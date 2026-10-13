"""permission.py 权限判定测试：拒绝列表、路径越界、MCP 策略、默认放行。

回归覆盖：
- check_permission 缺少兜底分支曾导致所有非 bash/MCP 工具被拦截
- 危险命令黑名单、路径越界检查
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from permission import (
    check_deny_list,
    check_mcp_permission,
    check_permission,
    check_rules,
)


class TestDenyList(unittest.TestCase):
    def test_dangerous_command_blocked(self):
        self.assertIsNotNone(check_deny_list("sudo rm -rf /"))

    def test_safe_command_allowed(self):
        self.assertIsNone(check_deny_list("echo hello"))


class TestCheckRules(unittest.TestCase):
    def test_del_command_flagged(self):
        self.assertIsNotNone(check_rules("run_bash", {"command": "del file.txt"}))

    def test_path_escape_flagged(self):
        # 绝对路径指向工作区外，应被拦
        self.assertIsNotNone(
            check_rules("run_read", {"path": "C:\\Windows\\win.ini"})
        )

    def test_normal_glob_no_flag(self):
        self.assertIsNone(check_rules("run_glob", {"pattern": "*.py"}))


class TestCheckPermission(unittest.TestCase):
    def test_default_tools_allow(self):
        """兜底分支：非 bash、非 MCP 工具应默认放行。"""
        self.assertTrue(check_permission("run_glob", {"pattern": "*.py"}))

    def test_bash_dangerous_denied(self):
        self.assertFalse(check_permission("run_bash", {"command": "rm -rf /"}))

    def test_mcp_allow_policy(self):
        self.assertTrue(check_mcp_permission("mcp__docs__search"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
