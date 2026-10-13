"""一次性子 agent（隔离上下文委托）。"""
from langchain.agents import create_agent
from tools import run_read, run_glob
from langchain_core.messages import HumanMessage

from langchain_core.tools import tool


@tool
def task(prompt: str) -> str:
    """派遣一个独立的一次性子代理，负责调查并仅返回最终摘要。"""
    from main import build_chat_model  # 延迟导入，断 main -> mcp -> subagents -> main 循环
    sub = create_agent(
        model=build_chat_model(),
        tools=[run_read, run_glob],
        system_prompt=(
            "你是一个专注的子代理。使用read/glob调查工作区，"
            "然后返回你发现的简要总结。不要提问。"
        )
    )
    try:
        result = sub.invoke({"messages": [HumanMessage(content=prompt)]})
        last = result["messages"][-1]
        return str(getattr(last, "content", last))
    except Exception as e:
        return f"subagent error: {e}"


