"""MCP 动态工具（连接发现 + 装配工具池）。"""
import functools
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from langchain_core.tools import tool, StructuredTool

from tools import WORKDIR
from hooks import register_hooks

dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if=", "> /dev/sda"]

def check_deny_list(command:str)-> str | None:
    for pattern in dangerous:
        if pattern in command:
            return f"被拒绝:{pattern} 在拒绝列表里面中"
    return None

def resolve_path(raw_path:str)-> Path:
    candidate=Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (WORKDIR/ candidate).resolve()


def check_rules(tool_name:str,args:dict)-> str | None:
    if tool_name=="run_bash":
        command=args.get("command","")
        if command.strip().lower().startswith("del") or any(kw in command for kw in ["rm ", "> /etc/", "chmod 777"]):
            return "潜在破坏命令"
    if tool_name in ("run_write","run_edit","run_read"):
        path=args.get("path","")
        if not resolve_path(path).is_relative_to(WORKDIR):
            return "路径超出工作目录范围"
    return None


def ask_user(tool_name:str,args:dict ,reason:str)-> bool:
    print(f"\nWarning{reason}")
    print(f"Tool:{tool_name}({args})")
    choice=input("Allow? (y/n):").strip().lower()
    return choice in ("y","yes")


MCP_HOST_POLICY={
    "mcp__docs__search": "allow",
    "mcp__docs__get_version": "allow",
    "mcp__deploy__status": "allow",
    "mcp__deploy__trigger": "confirm",
}


def check_mcp_permission(tool_name:str)->bool:
    decision =MCP_HOST_POLICY.get(tool_name,"comfirm")
    if decision=="allow":
        return True
    if decision=="deny":
        print(f"\n被阻止：MCP tool {tool_name} 应为主机策略被拒绝")
        return False
    if decision=="confirm":
        return ask_user(tool_name,{},f"外部mcp工具需要主机确认")



def check_permission(tool_name:str,args:dict)->bool:
    if tool_name.startswith("mcp__"):
        return check_mcp_permission(tool_name)
    if tool_name=="run_bash":
        reason=check_deny_list(args.get("command",""))
        if reason:
            print(f"\n被阻止：{reason}")
            return False
        reason=check_rules(tool_name,args)
        if reason:
            return ask_user(tool_name,args,reason)
        return True
    # 其他工具（read/write/edit/glob/todo/task/cron/skill 等）默认放行，
    # 其中 read/write/edit 仍走 check_rules 的路径越界检查。
    reason=check_rules(tool_name,args)
    if reason:
        return ask_user(tool_name,args,reason)
    return True



def on_pre_tool_use(tool_name, tool_args):
    # 实时精简版：只打工具名，参数留给 main 的回放，避免重复刷屏。
    if tool_name == "run_bash":
        cmd = tool_args.get("command", "")
        bg = " (background)" if tool_args.get("run_in_background") else ""
        print(f"   ⚙ {tool_name}: {cmd}{bg}")
    else:
        print(f"   ⚙ {tool_name}")
    if not check_permission(tool_name, tool_args):
        return "Permission denied"


def on_post_tool_use(tool_name, tool_args, result):
    print(f"   ✓ {tool_name}")


register_hooks("UserPromptSubmit", lambda c: None)  # 用户输入已在交互层显示，这里跳过
register_hooks("PreToolUse", on_pre_tool_use)
register_hooks("PostToolUse", on_post_tool_use)
register_hooks("Stop", lambda msgs: None)




