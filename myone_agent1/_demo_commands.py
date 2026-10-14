"""临时演示：真实运行 commands.py，展示各分发分支的输入/输出。用后即删。"""
import sys

sys.path.insert(0, "src")
from commands import Commands

cmds = Commands()

for inp in ["/help", "/h", "/com", "/nosuch", "!echo hello", "随便一句话"]:
    print(f"输入: {inp!r}")
    print(f"输出: {cmds.run(inp)!r}")
    print()
