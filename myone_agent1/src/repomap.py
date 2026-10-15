"""轻量代码地图：扫描工作区 .py 文件，提取函数/类，渲染成结构树。

借鉴 Aider repomap.py 的思路（解析 → 排序 → 渲染），但砍掉重型依赖：
- tree-sitter → 正则扫 `def` / `class`（够用的近似，语法无关）
- PageRank 排序 → 跳过（小项目直接按文件顺序列）
- 模型 tokenizer 预算 → 字符数近似（每 token ≈ 4 字符）

输出格式仿 Aider：`<repo_map> 文件路径 + 符号清单 </repo_map>`，
作为 system prompt 的一个区块，让模型开局就知道项目结构，不用逐个文件搜。

缓存（对齐 Aider 的 mtime 缓存思路，见其 repomap.py get_tags）：
- 指纹 = 每个 .py 文件的 (大小, mtime)，只读元数据、不打开文件内容
- 指纹没变 → 直接复用 .memory/repo_map_cache.json 里的上次地图文本，零扫描
- 任何文件增/删/改 → 指纹变化 → 全量重扫并写回缓存
- 缓存损坏/缺失 → 静默降级重扫，绝不让缓存拖垮主流程
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from tools import WORKDIR

# 匹配行首的 def / async def / class，并记录缩进与名字。
_SYMBOL_RE = re.compile(
    r"^(?P<indent> *)(?:(?:async +)?def|class) +(?P<name>\w+)\b",
    re.MULTILINE,
)

# 缓存格式版本：解析/渲染逻辑一变，旧缓存整体作废（仿 Aider 的 CACHE_VERSION）。
_CACHE_VERSION = 1
# 缓存文件相对项目根的路径（.memory 目录已在 .gitignore，不会提交到仓库）。
_CACHE_FILE = ".memory/repo_map_cache.json"


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


def _collect_py_files(root: Path) -> list:
    """收集参与地图的 .py 文件（排除 .memory / __pycache__ 运行时产物目录）。"""
    py_files = sorted(p for p in root.rglob("*.py"))
    return [
        p for p in py_files
        if ".memory" not in p.parts and "__pycache__" not in p.parts
    ]


def _fingerprint(root: Path):
    """项目指纹：每个 .py 文件的 (大小, mtime)，任何变化都会改变指纹。

    只读 stat 元数据而不打开文件——这正是缓存省时间的关键。
    某个文件读不到元数据时返回 None，表示"别走缓存，全量重扫"。
    """
    fp = {}
    for path in _collect_py_files(root):
        try:
            st = path.stat()
        except OSError:
            return None
        rel = str(path.relative_to(root)).replace("\\", "/")
        fp[rel] = [st.st_size, st.st_mtime]
    return fp


def _load_cache(cache_path: Path):
    """读缓存；文件缺失/JSON 损坏/版本不符 → 返回 None（静默降级重扫）。"""
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("version") != _CACHE_VERSION:
        return None
    return data


def _save_cache(cache_path: Path, fingerprint, text: str, max_chars: int) -> None:
    """写缓存；任何写入失败静默忽略——缓存可牺牲，主流程不能崩。"""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _CACHE_VERSION,
            "max_chars": max_chars,
            "fingerprint": fingerprint,
            "map": text,
        }
        cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _render_map(root: Path, max_chars: int) -> str:
    """真正的地图渲染：每个 .py 文件 + 符号清单，超预算截断。"""
    py_files = _collect_py_files(root)
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


def build_repo_map(root: Path = WORKDIR, max_chars: int = 8000, use_cache: bool = True) -> str:
    """生成项目代码地图，带指纹缓存。

    - 指纹没变 → 直接复用 .memory/repo_map_cache.json 里的上次文本（零扫描）
    - 指纹变了 / 缓存缺失损坏 / use_cache=False → 全量重扫；命中时写回缓存
    - max_chars 预算变化也会使缓存失效，避免复用错误截断的文本

    max_chars 是字符预算（≈ token 预算 * 4），防止地图撑爆上下文。
    """
    fingerprint = _fingerprint(root)
    cache_path = Path(root) / _CACHE_FILE

    if use_cache and fingerprint is not None:
        cached = _load_cache(cache_path)
        if (
            cached is not None
            and cached.get("max_chars") == max_chars
            and cached.get("fingerprint") == fingerprint
        ):
            return cached["map"]

    text = _render_map(root, max_chars)

    if use_cache and fingerprint is not None:
        _save_cache(cache_path, fingerprint, text, max_chars)
    return text
