"""Integrated Harness -- 很多机制，一个循环。

本章不再引入某个孤立的新机制，而是把前面章节的机制挂回同一条循环上：
基础工具 + Hook + 权限 + todo + skill + 记忆 + 一次性子 agent + 后台 bash + cron + MCP，
外加 system prompt 动态组装、上下文压缩和错误恢复。

因为要在运行时注入后台/定时通知、动态组装 MCP 工具，主循环仍然是手写的
，用 MODEL.bind_tools(assemble_tool_pool()) 每次取当前工具。
一次性子 agent（task 工具）则复用 create_agent，体现“隔离上下文”的委托。
"""



# os 读取环境变量。
import os
import time
import queue
from context_compact import compact_messages
from exceptions import classify
from cron_scheduler import CRON_QUEUE
from background_tasks import BACKGROUND_RESULTS
from hooks import trigger_hooks
import permission  # 导入即注册权限 Hook（UserPromptSubmit/PreToolUse/PostToolUse/Stop）
from mcp import CURRENT_TOOL_MAP,assemble_system_prompt,assemble_tool_pool
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage, SystemMessage

load_dotenv(override=True)

# 变量名与根目录 .env 保持一致（MODEL_NAME / OPENAI_API_KEY / BASE_URL）。
MODEL_NAME = os.getenv("MODEL_NAME", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("BASE_URL", "").strip() or None

# 尽早检查配置，比等到第一次模型请求时才得到难懂的供应商错误更清楚。
if not MODEL_NAME:
    raise RuntimeError("请在 .env 中设置 MODEL_NAME")
if not OPENAI_API_KEY:
    raise RuntimeError("请在 .env 中设置 OPENAI_API_KEY")

def build_chat_model()->ChatOpenAI:
    return ChatOpenAI(
        model=MODEL_NAME,
        max_completion_tokens=8000,
        temperature=0,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL

    )
MODEL = build_chat_model()

def call_model_with_recovery(system: str, messages: list, tools: list):
    """模型调用包裹恢复逻辑：临时失败指数退避重试，上下文过长则裁剪重试。"""
    llm = MODEL.bind_tools(tools)
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            return llm.invoke([SystemMessage(content=system)] + messages)
        except Exception as e:
            last_err = e
            info = classify(e)
            if info.is_context:
                # 上下文超长：裁剪后重试，不睡眠。
                messages = compact_messages(messages)
                print("[recover] trimmed context and retrying once")
            elif not info.retry:
                # 表里标了不可重试（key 错、参数错等）→ 直接抛出，不再退避。
                raise e
            else:
                wait = 2 ** attempt
                print(f"[recover] {info.hint}; retrying in {wait}s")
                time.sleep(wait)
    raise last_err


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
        print(f"[inject] {count} pending notification(s)")


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
                print(f"\033[33m{name}{args}\033[0m")
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

    history = []
    while True:
        try:
            query = input("\033[36ms15 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        history.append(HumanMessage(content=query))
        start = len(history)
        agent_loop(history)

        for message in history[start:]:
            print_tool_activity(message)
        last = last_assistant_message(history)
        if last is not None:
            print_assistant_message(last)
        print()

