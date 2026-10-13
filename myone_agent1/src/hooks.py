"""Hook 系统 + 权限（含 MCP 主机策略）。

实现时按需从 tools 导入：from tools import WORKDIR, resolve_path
"""


HOOKS={
    "UserPromptSubmit": [],
    "PreToolUse": [],
    "PostToolUse": [],
    "Stop": [],
}

def register_hooks(event:str,callback):
    # setdefault：事件不存在时先建空列表，避免 KeyError（支持注册任意新事件）。
    HOOKS.setdefault(event, []).append(callback)


def trigger_hooks(event:str,*args):
    for callback in HOOKS[event]:
        result=callback(*args)
        if result is not None:
            return result
    return None