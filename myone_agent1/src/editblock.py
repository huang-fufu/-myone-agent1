"""SEARCH/REPLACE 编辑格式：让模型用精确修改块改文件（对齐 Aider EditBlockCoder 的轻量版）。

格式（模型输出文本，或直接传结构化 edits）：

    <path>src/tools.py</path>
    <search>
    旧代码片段（必须与文件中内容完全一致，含缩进与空白）
    </search>
    <replace>
    新代码片段（替换进去）
    </replace>

设计要点（借鉴 Aider editblock_coder.py）：
- 先全部校验再统一写入：任一块失败 → 一个文件都不落盘（原子性）
- search 必须唯一匹配：找不到 → 报错；匹配多处 → 拒绝（防止误改）
- 失败报告仿 Aider SearchReplaceNoExactMatch，附最相似的真实行提示，让模型自我纠错
"""
import re
from difflib import SequenceMatcher
from pathlib import Path

from langchain_core.tools import tool

from repo import GitRepo
from tools import WORKDIR

# 匹配一对 <path>/<search>/<replace> 块；[\s\S] 保留内容原样（含缩进）。
_EDIT_BLOCK_RE = re.compile(
    r"<path>(?P<path>[\s\S]*?)</path>\s*"
    r"<search>(?P<search>[\s\S]*?)</search>\s*"
    r"<replace>(?P<replace>[\s\S]*?)</replace>",
    re.DOTALL,
)


def _strip_fences(text: str) -> str:
    """移除 markdown 代码围栏行（```lang / ```），容忍模型输出被围栏包裹。"""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("```")
    )


def parse_edits(text: str):
    """把模型回复解析成编辑列表，返回 (edits, errors)。

    edits 形如 [{"path": ..., "search": ..., "replace": ...}, ...]；
    格式残缺或没有任何块时，errors 给出原因。
    """
    text = _strip_fences(text)
    edits, errors = [], []
    for m in _EDIT_BLOCK_RE.finditer(text):
        path = m.group("path").strip()
        search = m.group("search").strip("\n")
        replace = m.group("replace").strip("\n")
        if not path:
            errors.append("存在缺少 <path> 的编辑块")
            continue
        edits.append({"path": path, "search": search, "replace": replace})
    if not edits and not errors:
        errors.append("未找到 <path>/<search>/<replace> 编辑块")
    return edits, errors


def _resolve(root: Path, raw_path: str) -> Path:
    """相对路径按 root 解析（工具场景 root=WORKDIR，测试可传临时目录）。"""
    p = Path(raw_path)
    if p.is_absolute():
        return p.resolve()
    return (root / p).resolve()


def _find_similar_line(search: str, content: str) -> str:
    """用 difflib 找文件里与 search 最相似的一行，失败时给模型纠错提示。"""
    best, best_ratio = "", 0.0
    for line in content.splitlines():
        ratio = SequenceMatcher(None, search, line).ratio()
        if ratio > best_ratio:
            best, best_ratio = line, ratio
    return best if best_ratio >= 0.5 else ""


def _report_success(planned) -> str:
    n = len(planned)
    blocks = "block" if n == 1 else "blocks"
    lines = [f"# {n} SEARCH/REPLACE {blocks} applied successfully."]
    for file_path, _ in planned:
        lines.append(f"{file_path}: updated")
    return "\n".join(lines)


def _report_failures(failures) -> str:
    n = len(failures)
    blocks = "block" if n == 1 else "blocks"
    res = [f"# {n} SEARCH/REPLACE {blocks} failed to match!"]
    for _, path, reason, search, content in failures:
        res.append(f"## SearchReplaceNoExactMatch: {reason} in {path or '(unknown)'}")
        similar = _find_similar_line(search, content) if content else ""
        if similar:
            res.append(f"Did you mean to match this actual line?\n{similar}")
    res.append(
        "SEARCH 必须与文件内容完全一致（含缩进、空白、注释）。请修正 SEARCH 后重试。"
    )
    return "\n".join(res)


def _git_fuse_report() -> str:
    """git 保险丝：工作区脏时拒绝编辑（仿 Aider 的 dirty 提示）。"""
    return (
        "# SEARCH/REPLACE edits blocked by git fuse\n"
        "git 仓库有未提交的变更，为避免混淆本次编辑与历史改动，已整批拒绝。\n"
        "请先处理工作区再重试 apply_edits：\n"
        "1. 提交当前改动：用 run_bash 执行 git add -A && git commit -m \"<msg>\"\n"
        "2. 或回滚上一次提交：调用 undo_last_change 工具\n"
        "工作区干净后，重新提交同样的 edits 即可。"
    )


def _try_auto_commit(root: Path, written_paths: list) -> str | None:
    """编辑全部落盘后，把本次涉及的文件自动提交。

    非 git 仓库或提交失败（如缺 git 身份）时静默降级：返回 None，不阻塞编辑。
    提交成功返回一行简短确认，供附加到成功报告。
    """
    try:
        repo = GitRepo(root)
        if not repo.is_repo():
            return None
        out = repo.commit_files(written_paths)
        lines = (out or "").strip().splitlines()
        return "auto-committed: " + (lines[-1] if lines else out)
    except Exception:
        return None  # 静默降级，绝不阻塞编辑


def apply_edits_core(edits, root: Path = WORKDIR, git_fuse: bool = True) -> str:
    """应用编辑列表。

    - 先对每个块做存在性 + 唯一性校验，全部通过才统一写入
    - 任一块失败 → 返回失败报告，一个文件都不改动
    - search 为空且文件不存在 → 视为新建文件
    - git_fuse：仓库工作区脏时先拒绝编辑（仿 Aider dirty 提示），
      编辑全部落盘后自动提交本次涉及的文件；非仓库/提交失败时静默跳过
    """
    if git_fuse:
        try:
            if GitRepo(root).is_dirty():
                return _git_fuse_report()
        except Exception:
            pass  # git 不可用/非仓库 → 跳过保险丝

    planned = []    # [(Path, 新内容)] 待统一写入
    failures = []   # [(索引, path, 原因, search, 文件原文)]

    for i, edit in enumerate(edits, 1):
        path = (edit.get("path") or "").strip()
        search = edit.get("search") or ""
        replace = edit.get("replace") or ""

        if not path:
            failures.append((i, "", "缺少 path 字段", search, ""))
            continue

        file_path = _resolve(root, path)

        # 新建文件：search 为空且文件不存在
        if not file_path.exists():
            if not search:
                planned.append((file_path, replace))
            else:
                failures.append((i, path, "文件不存在", search, ""))
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as e:
            failures.append((i, path, f"读取失败: {e}", search, ""))
            continue

        count = content.count(search)
        if count == 0:
            failures.append((i, path, "SEARCH 片段未找到", search, content))
        elif count > 1:
            failures.append((i, path, f"SEARCH 片段匹配 {count} 处，请补充更多上下文", search, content))
        else:
            planned.append((file_path, content.replace(search, replace, 1)))

    if failures:
        return _report_failures(failures)

    written = []
    for file_path, new_text in planned:
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(new_text, encoding="utf-8")
        except OSError as e:
            return f"Error: 写入 {file_path} 失败: {e}"
        written.append(file_path)

    report = _report_success(planned)
    if git_fuse:
        note = _try_auto_commit(root, written)
        if note:
            report += f"\n{note}"
    return report


@tool
def apply_edits(edits: list) -> str:
    """按 SEARCH/REPLACE 块精确修改文件，比整文件重写更安全。

    edits 是编辑列表，每项结构（JSON）：
    [{"path": "src/tools.py",
      "search": "旧代码片段，必须与文件中内容完全一致（含缩进与空白）",
      "replace": "新代码片段"}]

    规则：
    - 一个列表可同时改多个文件、多处修改
    - search 必须唯一匹配；找不到或不唯一会整批拒绝，一个文件都不改动
    - search 为空且文件不存在时，视为新建文件
    - 失败时会提示最相似的真实行，方便修正后重试
    - git 仓库工作区有未提交变更时整批拒绝（先提交，或调用 undo_last_change 回滚）
    - 编辑成功后自动提交本次涉及的文件（非 git 仓库或提交失败时自动跳过）
    """
    try:
        return apply_edits_core(edits)
    except Exception as e:
        return f"Error: {e}"
