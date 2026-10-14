"""commands.py 斜杠命令系统的测试：注册、分发、歧义/无效命令。

覆盖机制本身（不依赖真实 git / 子进程）：
- 命名即注册：cmd_ 方法自动出现在 get_commands()
- is_command：/ 和 ! 开头判定
- 前缀匹配：唯一匹配执行、多匹配报歧义、无匹配报无效
- do_run：未知命令报错
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from commands import Commands  # noqa: E402


class CommandsForTest(Commands):
    """去掉真实副作用：只保留 cmd_help 便于测试，其他命令覆盖机制即可。"""

    def cmd_help(self, args):
        """显示帮助"""
        return "help-output"


class TestCommands(unittest.TestCase):
    def setUp(self):
        self.cmds = CommandsForTest()

    # --- 注册机制 ---

    def test_cmd_method_auto_registered(self):
        self.assertIn("/help", self.cmds.get_commands())

    def test_commands_start_with_slash(self):
        for cmd in self.cmds.get_commands():
            self.assertTrue(cmd.startswith("/"))

    # --- 命令判定 ---

    def test_is_command_slash(self):
        self.assertTrue(self.cmds.is_command("/help"))
        self.assertFalse(self.cmds.is_command("hello"))
        self.assertFalse(self.cmds.is_command(""))

    def test_is_command_bang(self):
        self.assertTrue(self.cmds.is_command("!dir"))

    # --- 分发 ---

    def test_exact_command_runs(self):
        self.assertEqual(self.cmds.run("/help"), "help-output")

    def test_prefix_matching_runs(self):
        self.assertEqual(self.cmds.run("/hel"), "help-output")  # 前缀 /hel 唯一匹配

    def test_invalid_command_reports(self):
        out = self.cmds.run("/nosuch")
        self.assertIn("无效命令", out)

    def test_unknown_do_run_reports(self):
        out = self.cmds.do_run("nosuch", "")
        self.assertIn("不存在", out)

    def test_bang_routes_to_run(self):
        # !xxx -> do_run("run", "xxx")；覆盖 cmd_run 验证走对了分支。
        class BangCmds(Commands):
            def cmd_run(self, args):
                """跑命令"""
                return f"(run called with {args!r})"

        cmds = BangCmds()
        out = cmds.run("!echo hi")
        self.assertEqual(out, "(run called with 'echo hi')")


class TestAmbiguousCommand(unittest.TestCase):
    """两个同前缀且无精确命令 -> 报歧义；精确名仍可执行。"""

    class _Two(Commands):
        def cmd_foo_a(self, args):
            """A"""
            return "A"

        def cmd_foo_b(self, args):
            """B"""
            return "B"

    def test_ambiguous_prefix(self):
        cmds = self._Two()
        out = cmds.run("/foo")
        self.assertIn("歧义命令", out)
        self.assertIn("/foo-a", out)

    def test_exact_still_runs_when_ambiguous_prefix_exists(self):
        cmds = self._Two()
        self.assertEqual(cmds.run("/foo-a"), "A")


if __name__ == "__main__":
    unittest.main(verbosity=2)
