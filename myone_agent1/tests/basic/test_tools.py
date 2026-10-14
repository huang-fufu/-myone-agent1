"""tools.py 的只读功能测试：glob 递归、读取截断、缺失文件兜底、bash 输出格式。

回归覆盖（这几处都曾出过 bug）：
- run_glob 的 ** 静默返回空（缺 recursive=True）
- run_read 截断行尾缺右括号
- run_bash 长输出掐尾丢报错信息（改保留头尾 + 退出码前缀）
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from tools import _trim_output, run_bash, run_glob, run_read


class TestRunGlob(unittest.TestCase):
    def test_recursive_glob_finds_nested_files(self):
        """** 必须递归匹配 src/ 里的文件（曾静默返回空）。"""
        result = run_glob.invoke({"pattern": "**/*.py"})
        self.assertIn("tools.py", result)
        self.assertIn("main.py", result)

    def test_nonexistent_path_returns_no_matches(self):
        result = run_glob.invoke({"pattern": "definitely_not_here/**/*"})
        self.assertEqual(result, "(no matches)")

    def test_plain_glob_finds_src(self):
        result = run_glob.invoke({"pattern": "src/*.py"})
        self.assertIn("main.py", result)


class TestRunRead(unittest.TestCase):
    def test_limit_truncates_with_closing_paren(self):
        """截断提示必须以右括号结尾（曾输出 '...(N 更多行'）。"""
        result = run_read.invoke({"path": "src/tools.py", "limit": 5})
        lines = result.splitlines()
        self.assertEqual(len(lines), 6)
        self.assertTrue(lines[-1].endswith(")"), f"缺右括号: {lines[-1]!r}")

    def test_missing_file_returns_error(self):
        result = run_read.invoke({"path": "no_such_file.txt"})
        self.assertTrue(result.startswith("Error:"))


class TestRunBash(unittest.TestCase):
    def test_simple_command_returns_output_with_exit_code(self):
        """成功命令应带 [exit code 0] 前缀，方便模型判断成败。"""
        result = run_bash.invoke({"command": "echo hello"})
        self.assertIn("[exit code 0]", result)
        self.assertIn("hello", result)

    def test_failed_command_reports_nonzero_exit_code(self):
        """失败命令（退出码非 0）应如实上报退出码。"""
        result = run_bash.invoke({"command": 'python -c "import sys; sys.exit(3)"'})
        self.assertIn("[exit code 3]", result)

    def test_timeout_returns_clear_error(self):
        """超时分支应返回明确的超时提示而不是让主循环卡死。"""
        with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
            result = run_bash.invoke({"command": "sleep 999"})
        self.assertIn("超时", result)


class TestTrimOutput(unittest.TestCase):
    def test_short_output_untouched(self):
        """短于上限的输出原样返回。"""
        self.assertEqual(_trim_output("hi", 10), "hi")

    def test_long_output_keeps_head_and_tail(self):
        """长输出保留头尾 + 中间省略标记，不掐尾（报错常在尾部）。"""
        out = _trim_output("A" * 100, max_chars=20)
        self.assertIn("...(80 字符省略)...", out)
        self.assertIn(out.splitlines()[-1][-1], "A")  # 尾部保留
        self.assertEqual(len(out.splitlines()), 3)   # 头 + 省略 + 尾


if __name__ == "__main__":
    unittest.main(verbosity=2)
