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


@tool
def run_bash(command:str,run_in_background:bool=False)->str:
    """执行一个shell命令。设置run_in_background=True以异步运行并返回占用符。"""
    if run_in_background:
        from background_tasks import start_background_task   # 延迟导入，断顶层循环
        return start_background_task(command)

    try:
        r=subprocess.run(command,shell=True,cwd=WORKDIR,capture_output=True,text=True,encoding="utf-8",errors="replace")
        out=(r.stdout+r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except OSError as e:
        return f"Error: {e}"
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
