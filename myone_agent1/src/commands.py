"""斜杠命令系统：任何 cmd_xxx 方法自动变成 /xxx 命令。

机制三件套：
- 命名即注册：定义 `def cmd_foo(self, args)` 就自动有 `/foo` 命令，零注册代码
- 前缀匹配分发：`/com` 可匹配 `/commit`；多个匹配报 Ambiguous，无匹配报 Invalid
- docstring 即帮助：每个命令的 docstring 会出现在 `/help` 里

主循环用法：用户输入以 `/` 开头时不走模型，直接命令分发（省 token、响应快）。
"""
import subprocess

from tools import WORKDIR, run_bash
from repo import GitRepo


class Commands:
    # ------------------------------------------------------------------
    # 注册与分发机制（与具体命令无关，新增命令只需加一个 cmd_ 方法）
    # ------------------------------------------------------------------

    def get_commands(self) -> list:
        """扫描类里所有 cmd_ 开头的方法，生成 ['/commit', '/help', ...]。"""
        commands = []
        for attr in dir(self):
            if not attr.startswith("cmd_"):
                continue
            cmd = attr[4:].replace("_", "-")   # cmd_commit -> commit -> /commit
            commands.append("/" + cmd)
        return sorted(commands)

    def is_command(self, inp: str) -> bool:
        """判断输入是不是命令：/ 开头是命令，! 开头是直通 shell。"""
        return bool(inp) and inp[0] in "/!"

    def matching_commands(self, inp: str):
        """前缀匹配：把输入拆成'首词'和'剩余参数'，找首词能匹配到的命令。"""
        words = inp.strip().split()
        if not words:
            return None
        first_word = words[0]
        rest_inp = inp[len(words[0]):].strip()
        all_commands = self.get_commands()
        matching = [c for c in all_commands if c.startswith(first_word)]
        return matching, first_word, rest_inp

    def do_run(self, cmd_name: str, args: str):
        """动态执行：'commit' -> getattr(self, 'cmd_commit') -> 调用它。"""
        method_name = f"cmd_{cmd_name.replace('-', '_')}"
        method = getattr(self, method_name, None)
        if method is None:
            return f"错误：命令 {cmd_name} 不存在"
        try:
            return method(args)
        except Exception as e:
            return f"命令 {cmd_name} 执行失败：{e}"

    def run(self, inp: str):
        """分发入口：! 直通 shell；/ 前缀匹配后执行。"""
        if inp.startswith("!"):
            return self.do_run("run", inp[1:])

        res = self.matching_commands(inp)
        if res is None:
            return
        matching, first_word, rest_inp = res

        if len(matching) == 1:
            return self.do_run(matching[0][1:], rest_inp)
        if first_word in matching:          # 首词本身是完整命令（如 /help）
            return self.do_run(first_word[1:], rest_inp)
        if len(matching) > 1:
            return f"歧义命令：{', '.join(matching)}，请写完整"
        return f"无效命令：{first_word}（/help 查看可用命令）"

    # ------------------------------------------------------------------
    # 具体命令（新增命令：加一个 cmd_ 方法即可）
    # ------------------------------------------------------------------

    def cmd_help(self, args):
        """显示所有可用命令"""
        lines = []
        for cmd in self.get_commands():
            method = getattr(self, "cmd_" + cmd[1:].replace("-", "_"))
            lines.append(f"{cmd}  -  {method.__doc__}")
        return "\n".join(lines) or "(暂无命令)"

    def cmd_commit(self, args):
        """提交工作区变更（可选消息：/commit 修复bug；不带则自动生成）"""
        repo = GitRepo(WORKDIR)
        if not repo.is_repo():
            return "错误：当前目录不是 git 仓库"
        if not repo.is_dirty():
            return "工作区干净，没有需要提交的变更"
        repo.add()
        return repo.commit(args.strip() or None)

    def cmd_log(self, args):
        """查看最近 5 条提交记录"""
        repo = GitRepo(WORKDIR)
        if not repo.is_repo():
            return "错误：当前目录不是 git 仓库"
        return repo.log(5)

    def cmd_test(self, args):
        """运行全部单元测试（tests/basic）"""
        r = subprocess.run(
            "python run_tests.py", shell=True, cwd=WORKDIR,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        out = (r.stdout + r.stderr).strip()
        return out[-3000:] if out else "(无输出)"

    def cmd_run(self, args):
        """执行 shell 命令（! 开头等价于 /run，不走模型）"""
        return run_bash.invoke({"command": args})
