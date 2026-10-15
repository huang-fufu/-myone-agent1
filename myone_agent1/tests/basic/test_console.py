"""console.py IO 交互抽象的测试。

回归覆盖：
- read_input 读取用户输入
- tool_output 打印到 stdout
- confirm 的 y/n/空回车默认/非法输入循环重问
"""
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from console import IO


class TestIO(unittest.TestCase):
    def setUp(self):
        self.io = IO()

    def test_read_input_returns_user_typed(self):
        with patch("builtins.input", return_value="hello"):
            self.assertEqual(self.io.read_input("> "), "hello")

    def test_tool_output_prints_to_stdout(self):
        out = StringIO()
        with redirect_stdout(out):
            self.io.tool_output("tool result here")
        self.assertIn("tool result here", out.getvalue())

    def test_confirm_yes_is_true(self):
        with patch("builtins.input", return_value="y"):
            self.assertTrue(self.io.confirm("继续?"))

    def test_confirm_no_is_false(self):
        with patch("builtins.input", return_value="n"):
            self.assertFalse(self.io.confirm("继续?"))

    def test_confirm_empty_uses_default(self):
        with patch("builtins.input", return_value=""):
            self.assertTrue(self.io.confirm("继续?", default=True))
        with patch("builtins.input", return_value=""):
            self.assertFalse(self.io.confirm("继续?", default=False))

    def test_confirm_retries_on_invalid_input(self):
        with patch("builtins.input", side_effect=["x", "yes"]):  # 非法后重问
            self.assertTrue(self.io.confirm("继续?"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
