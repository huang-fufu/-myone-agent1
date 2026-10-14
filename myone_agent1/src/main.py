"""Integrated Harness -- 很多机制，一个循环。

本章不再引入某个孤立的新机制，而是把前面章节的机制挂回同一条循环上：
基础工具 + Hook + 权限 + todo + skill + 记忆 + 一次性子 agent + 后台 bash + cron + MCP，
外加 system prompt 动态组装、上下文压缩和错误恢复。

因为要在运行时注入后台/定时通知、动态组装 MCP 工具，主循环仍然是手写的
，用 MODEL.bind_tools(assemble_tool_pool()) 每次取当前工具。
一次性子 agent（task 工具）则复用 create_agent，体现“隔离上下文”的委托。
"""



# os 读取环境变量。
import json
import os
import time
import queue
from context_compact import compact_messages
from exceptions import classify
from tools import WORKDIR
from cron_scheduler import CRON_QUEUE
from background_tasks import BACKGROUND_RESULTS
from hooks import trigger_hooks
import permission  # 导入即注册权限 Hook（UserPromptSubmit/PreToolUse/PostToolUse/Stop）
from logging_setup import get_logger
from mcp import CURRENT_TOOL_MAP,assemble_system_prompt,assemble_tool_pool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage, SystemMessage

from config import CONFIG

API_KEY_INDEX = [0]  # 当前使用的 key 下标（运行时状态，非配置）

def build_chat_model()->ChatOpenAI:
    return ChatOpenAI(
        model=CONFIG.model_name,
        max_completion_tokens=8000,
        temperature=0,
        api_key=CONFIG.api_keys[API_KEY_INDEX[0]],
        base_url=CONFIG.base_url

    )
MODEL = build_chat_model()


def rotate_api_key():
    """限流时切换到下一个 key 并重建 model；只有一个 key 时无操作。"""
    if len(CONFIG.api_keys) <= 1:
        return
    API_KEY_INDEX[0] = (API_KEY_INDEX[0] + 1) % len(CONFIG.api_keys)
    global MODEL
    MODEL = build_chat_model()
    log.warning("已切换到第 %d 个 API key", API_KEY_INDEX[0] + 1)

log = get_logger("main")


def call_model_with_recovery(system: str, messages: list, tools: list):
    """模型调用包裹恢复逻辑：临时失败指数退避重试，上下文过长则裁剪重试。"""
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            llm = MODEL.bind_tools(tools)  # 每次重新 bind，保证轮换 key 后下一轮生效
            return llm.invoke([SystemMessage(content=system)] + messages)
        except Exception as e:
            last_err = e
            info = classify(e)
            if info.is_context:
                # 上下文超长：裁剪后重试，不睡眠。
                messages = compact_messages(messages)
                log.warning("context 超长，已裁剪重试")
            elif not info.retry:
                # 表里标了不可重试（key 错、参数错等）→ 直接抛出，不再退避。
                raise e
            else:
                # 限流 → 先切下一个 key，再退避重试。
                if type(e).__name__ == "RateLimitError":
                    rotate_api_key()
                wait = 2 ** attempt
                log.warning("%s；%ds 后重试", info.hint, wait)
                time.sleep(wait)
    raise last_err


# ---------------------------------------------------------------------------
# 会话持久化：照抄 Aider append_chat_history 思路（追加写盘 + 失败降级）
# ---------------------------------------------------------------------------

HISTORY_FILE = WORKDIR / ".memory" / "history.jsonl"
# 恢复时最多取最近 N 条，避免历史无限累积导致上下文超长。
HISTORY_LIMIT = 20


def append_history_entry(role: str, content: str) -> None:
    """把一条对话记录追加到历史文件（只存 user/assistant 文本，不存工具调用）。"""
    global HISTORY_FILE
    if HISTORY_FILE is None:
        return
    if not content:
        return  # 空内容（模型只调工具不输出文本）不写入，避免污染历史
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        with HISTORY_FILE.open("a", encoding="utf-8", errors="ignore") as f:
            f.write(line + "\n")
    except (PermissionError, OSError) as err:
        log.warning("history 写入失败，已禁用：%s", err)
        HISTORY_FILE = None


def load_history() -> list:
    """启动时把历史文件读回成消息列表（损坏行跳过）。"""
    if HISTORY_FILE is None or not HISTORY_FILE.exists():
        return []
    msgs = []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role, content = entry.get("role"), entry.get("content", "")
                if role == "user":
                    msgs.append(HumanMessage(content=content))
                elif role == "assistant":
                    msgs.append(AIMessage(content=content))
    except (PermissionError, OSError) as err:
        log.warning("history 读取失败：%s", err)
    return msgs[-HISTORY_LIMIT:]


def inject_pending(messages: list) -> None:
    """把已完成的后台任务通知和到期 cron prompt 注入消息流。"""
    count = 0
    while True:
        try:
            item = BACKGROUND_RESULTS.get_nowait()
        except queue.Empty:
            break
        messages.append(HumanMessage(content=item))
        count += 1
    while True:
        try:
            item = CRON_QUEUE.get_nowait()
        except queue.Empty:
            break
        messages.append(HumanMessage(content=f"<cron reminder>{item}</cron reminder>"))
        count += 1
    if count:
        log.info("注入 %d 条待处理通知", count)


def execute_tool_calls(response: AIMessage) -> list:
    """执行一条模型消息里的所有工具调用，插入 Hook 与权限。"""
    outputs = []
    for tool_call in response.tool_calls:
        name = tool_call["name"]
        args = tool_call.get("args", {})

        blocked = trigger_hooks("PreToolUse", name, args)
        if blocked:
            outputs.append(ToolMessage(content=str(blocked), tool_call_id=tool_call["id"], name=name, status="error"))
            continue

        tool = CURRENT_TOOL_MAP.get(name)
        if tool is None:
            output = f"Error: unknown tool {name}"
        else:
            try:
                output = tool.invoke(args)
            except Exception as e:
                output = f"Error: {e}"

        result = ToolMessage(content=str(output), tool_call_id=tool_call["id"], name=name)
        trigger_hooks("PostToolUse", name, args, result)
        outputs.append(result)
    return outputs


def agent_loop(messages: list) -> None:
    if messages:
        trigger_hooks("UserPromptSubmit", getattr(messages[-1], "content", messages[-1]))

    while True:
        # 1. 注入后台/定时通知。
        inject_pending(messages)

        # 2. 组装 system prompt（记忆 + skills + MCP 状态）。
        query_text = str(getattr(messages[-1], "content", ""))
        system = assemble_system_prompt(query_text)

        # 3. 取当前工具池，带恢复地调用模型。
        tools = assemble_tool_pool()
        response = call_model_with_recovery(system, messages, tools)
        messages.append(response)

        # 4. 没有工具调用 → Stop → 结束本轮。
        if not response.tool_calls:
            trigger_hooks("Stop", messages)
            return

        # 5. 执行工具，把结果追加回消息流，继续循环。
        messages.extend(execute_tool_calls(response))


# ---------------------------------------------------------------------------
# 打印与交互
# ---------------------------------------------------------------------------

def print_assistant_message(message: AIMessage) -> None:
    content = message.content
    if isinstance(content, str):
        print(content)
        return
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    print(block.get("text", ""))
            elif hasattr(block, "text"):
                print(block.text)


def print_tool_activity(message) -> None:
    if isinstance(message, AIMessage):
        for tool_call in message.tool_calls:
            name = tool_call["name"]
            args = tool_call.get("args", {})
            if name == "run_bash":
                bg = " (background)" if args.get("run_in_background") else ""
                print(f"\033[33m$ {args.get('command', '')}{bg}\033[0m")
            else:
                # 精简回放：show 只留关键参数，避免整个 dict 平铺刷屏。
                show = {k: args[k] for k in ("path", "pattern", "command") if k in args}
                print(f"\033[33m{name}{show if show else ''}\033[0m")
        return
    if isinstance(message, ToolMessage):
        content = str(message.content)
        if getattr(message, "status", None) == "error":
            print(f"(blocked/error) {content[:200]}")
        else:
            print(content[:200])


def last_assistant_message(messages: list) -> AIMessage | None:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            return m
    return None


if __name__ == "__main__":
    print("s15: Integrated Harness")
    print("输入问题，回车发送。输入 q 退出。\n")

    history = load_history()
    print(f"[history] 已恢复 {len(history)} 条对话记录\n")

    while True:
        try:
            query = input("\033[36ms15 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append(HumanMessage(content=query))
        append_history_entry("user", query)
        start = len(history)
        agent_loop(history)

        for message in history[start:]:
            print_tool_activity(message)
        last = last_assistant_message(history)
        if last is not None:
            print_assistant_message(last)
            content = last.content
            if isinstance(content, str):
                append_history_entry("assistant", content)
            elif isinstance(content, list):
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif hasattr(block, "text"):
                        texts.append(block.text)
                append_history_entry("assistant", "\n".join(t for t in texts if t))
        print()

