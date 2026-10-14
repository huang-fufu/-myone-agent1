"""轻量代码地图：扫描工作区 .py 文件，提取函数/类，渲染成结构树。

借鉴 Aider repomap.py 的思路（解析 → 排序 → 渲染），但砍掉重型依赖：
- tree-sitter → 正则扫 `def` / `class`（够用的近似，语法无关）
- PageRank 排序 → 跳过（小项目直接按文件顺序列）
- 模型 tokenizer 预算 → 字符数近似（每 token ≈ 4 字符）

输出格式仿 Aider：`<repo_map> 文件路径 + 符号清单 </repo_map>`，
作为 system prompt 的一个区块，让模型开局就知道项目结构，不用逐个文件搜。
"""
import re
from dataclasses import dataclass
from pathlib import Path

from tools import WORKDIR

# 匹配行首的 def / async def / class，并记录缩进与名字。
_SYMBOL_RE = re.compile(
    r"^(?P<indent> *)(?:(?:async +)?def|class) +(?P<name>\w+)\b",
    re.MULTILINE,
)


@dataclass
class Symbol:
    name: str
    kind: str  # "def" / "class"
    line: int
    indent: int


def _extract_symbols(text: str) -> list:
    """从源码文本提取符号（跳过单下划线私有成员，保留 __init__ 等魔术方法）。"""
    symbols = []
    for m in _SYMBOL_RE.finditer(text):
        name = m.group("name")
        if name.startswith("_") and not name.startswith("__"):
            continue
        prefix = m.group(0).lstrip()
        kind = "class" if prefix.startswith("class") else "def"
        line = text.count("\n", 0, m.start()) + 1
        symbols.append(Symbol(name=name, kind=kind, line=line, indent=len(m.group("indent"))))
    return symbols


def scan_file(path: Path) -> str:
    """单个文件的符号清单，如 'def run_bash (L47)'；顶层符号顶格，类内方法缩进两格。"""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = []
    for s in _extract_symbols(text):
        pad = "" if s.indent == 0 else "  "
        lines.append(f"{pad}{s.kind} {s.name} (L{s.line})")
    return "\n".join(lines)


def build_repo_map(root: Path = WORKDIR, max_chars: int = 8000) -> str:
    """生成项目代码地图：每个 .py 文件 + 符号清单，超预算截断。

    max_chars 是字符预算（≈ token 预算 * 4），防止地图撑爆上下文。
    """
    py_files = sorted(p for p in root.rglob("*.py"))
    # 排除运行时产物目录。
    py_files = [
        p for p in py_files
        if ".memory" not in p.parts and "__pycache__" not in p.parts
    ]
    if not py_files:
        return "(no python files)"

    parts = ["<repo_map>"]
    for path in py_files:
        rel = str(path.relative_to(root)).replace("\\", "/")
        body = scan_file(path)
        if body:
            parts.append(f"{rel}\n{body}")
    text = "\n".join(parts) + "\n</repo_map>"

    if len(text) > max_chars:
        text = text[:max_chars] + "\n...(map truncated)...\n</repo_map>"
    return text
