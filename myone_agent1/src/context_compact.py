"""s15 上下文压缩（裁剪过长工具结果）。"""
from typing import Any

from langchain_core.messages import ToolMessage
MAX_TOOL_CHARS = 20000
MAX_SINGLE_TOOL_CHARS = 4000
def compact_messages(messages: list) -> list:
    """把过长的单个工具结果截断，并给累计工具结果设一个总预算。"""
    out: list = []
    tool_chars = 0
    for m in messages:
        if isinstance(m, ToolMessage):
            c = str(m.content)
            if len(c) > MAX_SINGLE_TOOL_CHARS:
                c = c[:MAX_SINGLE_TOOL_CHARS] + "\n...(snipped)"
            tool_chars += len(c)
            if tool_chars > MAX_TOOL_CHARS:
                c = c[:500] + "\n...(further compacted)"
            out.append(ToolMessage(content=c, tool_call_id=m.tool_call_id, name=m.name))
        else:
            out.append(m)
    return out