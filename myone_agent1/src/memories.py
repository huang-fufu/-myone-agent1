from tools import WORKDIR
"""
实现时按需从 tools 导入：from tools import WORKDIR（MEMORY_DIR = WORKDIR / ".memory"）
"""

MEMORY_DIR = WORKDIR / ".memory"

def memory_section(query_text:str="") ->str:
    """把 .memory/MEMORY.md 里相关的记录注入 system prompt。"""
    mem_file=MEMORY_DIR/"MEMORY.md"
    if not(mem_file.exists()):
        return "Long-term memory: (空)"
    try:
        lines=mem_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return "Long-term memory: (读取失败)"

    if query_text:
        kws=[w for w in query_text.lower().split() if len(w)>3]
        relevant = [ln for ln in lines if kws and any(k in ln.lower() for k in kws)]
        selected = relevant if relevant else lines
    else:
        selected = lines
    return "Long-term memory (relevant):\n" + "\n".join(selected[:50])
