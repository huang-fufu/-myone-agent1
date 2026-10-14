"""s15 基础工具：路径解析 + 文件/命令工具。

WORKDIR 唯一在这里定义，其它模块统一 `from tools import WORKDIR, ...`，
tools.py 顶层无循环依赖（仅 run_bash 内部延迟导入 background_tasks）。
"""
from pathlib import Path
import glob as g
import os, subprocess

from langchain_core.tools import tool

# 唯一的工作目录来源（相对启动目录解析，保证 resolve 后为绝对路径）。
WORKDIR = Path.cwd().resolve()


def resolve_path(raw_path: str) -> Path:
    """把用户给的路径解析成绝对路径；越界检查由 permission.check_rules 负责。"""
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (WORKDIR / candidate).resolve()


_BASH_DESC = """
平台提示（重要）：本机是 Windows，命令由 cmd.exe（shell=True）执行，
不是 Linux/bash：
- 用 `dir` 而非 `ls`，用 `type` 而非 `cat`，用 `findstr` 而非 `grep`
- 路径用反斜杠（C:\\xxx），不要写 /c/xxx 或 /home/ 这种 Linux 风格
- 当前工作目录（WORKDIR）= {workdir}，命令默认在此目录执行
- 不要使用 $()、$(command)、单引号展开等 bash 语法，它们不会被解析
- 可以用 `&` 连接多条命令"""


def _trim_output(out: str, max_chars: int = 50000) -> str:
    """长输出保留头尾 + 中间省略——报错信息（traceback）常在尾部，掐尾会丢关键信息。

    Aider 不截断输出，靠"决策层"控制注入；agent 无法每步问人，
    所以这里自动截断，但保留头尾让模型能看到尾部报错。
    """
    if len(out) <= max_chars:
        return out
    head = out[: max_chars // 2]
    tail = out[-max_chars // 2 :]
    return f"{head}\n...({len(out) - max_chars} 字符省略)...\n{tail}"


@tool
def run_bash(command: str, run_in_background: bool = False) -> str:
    """执行一个shell命令。设置run_in_background=True以异步运行并返回占用符。"""
    if run_in_background:
        from background_tasks import start_background_task   # 延迟导入，断顶层循环
        return start_background_task(command)

    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        out = _trim_output((r.stdout + r.stderr).strip())
        # 返回退出码前缀，让模型能判断命令成败（借鉴 Aider 的 (code, output) 思路）。
        if not out:
            return f"[exit code {r.returncode}] (no output)"
        return f"[exit code {r.returncode}]\n{out}"
    except subprocess.TimeoutExpired:
        return "Error: 命令执行超时（>120 秒），已终止"
    except OSError as e:
        return f"Error: {e}"


# 装饰后覆盖 description，把 WORKDIR 动态填进平台提示（@tool 无法用 f-string docstring）。
run_bash.description = run_bash.description.split("。")[0] + "。" + _BASH_DESC.format(workdir=WORKDIR)
@tool
def run_read(path:str,limit:int | None=None)->str:
    """读取一个UTF-8文本文件，可选地限制返回的行数。"""
    try:
        lines=resolve_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines=lines[:limit]+[f"...({len(lines)-limit} 更多行)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"

@tool
def run_write(path:str,content:str)->str:
    """UTF-8编码的内容写入文件，替换其现有内容。"""
    try:
        file_path=resolve_path(path)
        file_path.parent.mkdir(parents=True,exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"写 {len(content)} 字节 到 {path}"
    except Exception as e:
        return f"Error: {e}"


@tool
def run_edit(path:str,old_text:str,new_text:str)->str:
    """在UTF-8文件中替换第一次精确匹配的old_text。"""
    try:
        file_path=resolve_path(path)
        text=file_path.read_text(encoding="utf-8")
        if old_text not in text:
            return f"错误：在 {path} 中未找到文本"
        file_path.write_text(text.replace(old_text,new_text,1), encoding="utf-8")
        return f"编辑 {path}"
    except Exception as e:
        return f"Error: {e}"


@tool
def run_glob(pattern:str)->str:
    """查找与通配符模式匹配的工作区文件。"""
    try:
        results=[]
        for match in g.glob(pattern,root_dir=WORKDIR,recursive=True):
            if (WORKDIR/match).resolve().is_relative_to(WORKDIR):
                results.append(match)
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"
