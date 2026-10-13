"""tools.py 的只读功能测试：glob 递归、读取截断、缺失文件兜底。

回归覆盖（这几处都曾出过 bug）：
- run_glob 的 ** 静默返回空（缺 recursive=True）
- run_read 截断行尾缺右括号
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from tools import run_bash, run_glob, run_read


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
    def test_simple_command_returns_output(self):
        result = run_bash.invoke({"command": "echo hello"})
        self.assertEqual(result, "hello")


if __name__ == "__main__":
    unittest.main(verbosity=2)
