"""s15 待办列表（todo_write）。"""
from langchain_core.tools import tool
# 当前会话的待办列表，元素形如 {"content": str, "status": str}。
TODO:list[dict]=[]

@tool
def todo_write(todos:list[dict]) ->str:
    """将当前待办事项列表替换为新列表。

    每项必须是字典，包含 content 和 status：
    {"content": "任务内容", "status": "pending|in_progress|completed"}

    示例:
    todos=[{"content":"创建 demo.txt","status":"pending"},
           {"content":"读回内容","status":"pending"}]
    """
    global TODO
    if not isinstance(todos, list):
        return "Error: 待办事项必须是一个列表，每项为 {\"content\": ..., \"status\": ...}"
    cleaned=[]
    for item in todos:
        if isinstance(item, dict) and "content" in item:
            cleaned.append({"content":item["content"],"status":item.get("status", "pending")})
    TODO=cleaned
    return f"todo updated: {len(TODO)} item(s)"

