"""linter.py 轻量版语法检查的测试。

回归覆盖：
- 无错代码返回 None（lint_python_compile 与 lint 双入口）
- 语法错误返回"给模型看的修复指令"，开头是 # Fix any errors below
- 出错行号记录正确（0 基）
- 文件不存在/读不到返回 None
- 中文内容能正常处理（ensure 编码容错）
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from linter import LintResult, lint, lint_python_compile  # noqa: E402


class TestLintPythonCompile(unittest.TestCase):
    def test_clean_code_returns_none(self):
        code = "def foo():\n    return 1\n"
        self.assertIsNone(lint_python_compile("a.py", code))

    def test_syntax_error_returns_result(self):
        code = "def foo(:\n    pass\n"
        res = lint_python_compile("a.py", code)
        self.assertIsInstance(res, LintResult)
        self.assertIn("SyntaxError", res.text)
        self.assertIn("a.py", res.text)  # traceback 里有文件名

    def test_line_numbers_zero_based(self):
        code = "x = 1\ny = 2\ndef broken(:\n"
        res = lint_python_compile("a.py", code)
        self.assertEqual(res.lines, [2])  # 第 3 行出错 → 0 基是 2


class TestLint(unittest.TestCase):
    def _write(self, tmp: str, content: str) -> str:
        p = Path(tmp) / "mod.py"
        p.write_text(content, encoding="utf-8")
        return str(p)

    def test_clean_file_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            fname = self._write(tmp, "print('ok')\n")
            self.assertIsNone(lint(fname))

    def test_broken_file_returns_fix_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            fname = self._write(tmp, "def foo(:\n    pass\n")
            text = lint(fname)
        self.assertIsNotNone(text)
        self.assertTrue(text.startswith("# Fix any errors below, if possible."))
        self.assertIn("SyntaxError", text)

    def test_missing_file_returns_none(self):
        self.assertIsNone(lint(str(Path(tempfile.gettempdir()) / "no_such_file_xyz.py")))

    def test_utf8_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            fname = self._write(tmp, "# 中文注释\ndef 名字():\n    pass\n")
            self.assertIsNone(lint(fname))  # 合法的 unicode 标识符不报错


if __name__ == "__main__":
    unittest.main(verbosity=2)
