"""IO 交互抽象：收口所有输入输出。

把 input / print / confirm 收口成一个类，主循环只跟 IO 实例打交道。
好处：将来加颜色、加 GUI、加静默模式，只改这一个类，所有调用点不动。

命名注意：模块叫 console 而非 io，避免与标准库 io 模块冲突——
项目与 langchain 同进程，标准库 io 会被提前加载，同名的会拿不到自己的类。

confirm 规范化返回布尔：y/yes → True，n/no → False，回车 → 默认值，
非法输入会循环重问而不是崩溃。
"""
from __future__ import annotations


class IO:
    def read_input(self, prompt: str = "") -> str:
        """读一行用户输入。"""
        return input(prompt)

    def tool_output(self, msg: str) -> None:
        """打印工具结果 / 系统消息（默认直接 print）。"""
        print(msg)

    def confirm(self, question: str, default: bool = True) -> bool:
        """y/n 确认；回车走默认值，非法输入循环重问。"""
        hint = "[Y/n]" if default else "[y/N]"
        while True:
            answer = input(f"{question} {hint} ").strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            # 非法输入：继续问，不猜测、不崩溃
