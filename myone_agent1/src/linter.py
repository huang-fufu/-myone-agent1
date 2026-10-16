"""轻量版 linter —— 只用 Python 内置能力，零第三方依赖。

定位：自动查错闭环的一环。
模型改完 .py 文件后，用 lint() 检查语法，把错误文本喂回模型，模型照着修。

设计取舍：
- 保留：内置 compile() 查语法错误（零依赖，SyntaxError traceback 自带出错行 + ^ 指示）
- 砍掉：tree-sitter 语法树（重依赖）、flake8 外部命令（需安装）、tree_context 渲染
  （与 repomap 用正则替代 tree-sitter 的降级思路一致）

输出开头那句 "# Fix any errors below, if possible." 是给模型的指令。
"""

import traceback
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LintResult:
    """一次查错的结果：错误文本 + 出错行号（0 基，供将来高亮/定位用）。"""

    text: str
    lines: list


def _read_code(fname: str) -> str | None:
    """读文件内容；读失败（不存在/权限）返回 None 并打印原因。"""
    try:
        return Path(fname).read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        print(f"Unable to read {fname}: {err}")
        return None


def lint_python_compile(fname: str, code: str) -> LintResult | None:
    """用 Python 内置 compile() 查语法错误。

    compile(code, fname, "exec") 等价于"编译后直接丢弃"：
    语法有错会抛异常（拿到 traceback 和行号），没错则无副作用地通过。
    """
    try:
        compile(code, fname, "exec")
        return None
    except Exception as err:
        end_lineno = getattr(err, "end_lineno", err.lineno)
        line_numbers = list(range(err.lineno - 1, end_lineno))
        text = "".join(traceback.format_exception(type(err), err, err.__traceback__))
        return LintResult(text=text, lines=line_numbers)


def lint(fname: str) -> str | None:
    """对一个 .py 文件做语法检查。

    返回给模型看的修复指令文本；文件没问题（或读不到）返回 None。
    """
    code = _read_code(fname)
    if code is None:
        return None
    result = lint_python_compile(fname, code)
    if result is None:
        return None
    return f"# Fix any errors below, if possible.\n\n{result.text}"
