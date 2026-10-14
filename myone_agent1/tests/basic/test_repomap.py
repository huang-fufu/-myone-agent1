"""repomap.py 轻量代码地图的测试：符号提取、地图生成、预算截断。

回归覆盖：
- 正则能抓顶层 def/class、async def、类内方法
- 跳过单下划线私有符号，保留 __init__ 魔术方法
- build_repo_map 按文件渲染、排除 .memory / __pycache__、超预算截断
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from repomap import _extract_symbols, build_repo_map, scan_file


SAMPLE = '''\
"""模块 docstring"""
import os

def run_bash(command, timeout=120):
    "工具 docstring"
    return os.system(command)

async def run_long_task():
    pass

class GitRepo:
    def __init__(self, root):
        self.root = root

    def commit(self, msg):
        return self.root

    def _private_helper(self):
        pass
'''


class TestExtractSymbols(unittest.TestCase):
    def test_finds_defs_class_and_methods(self):
        names = [s.name for s in _extract_symbols(SAMPLE)]
        self.assertIn("run_bash", names)
        self.assertIn("run_long_task", names)   # async def
        self.assertIn("GitRepo", names)          # class
        self.assertIn("commit", names)           # 类内方法

    def test_kind_classified(self):
        by_name = {s.name: s for s in _extract_symbols(SAMPLE)}
        self.assertEqual(by_name["GitRepo"].kind, "class")
        self.assertEqual(by_name["run_bash"].kind, "def")

    def test_private_skipped_dunder_kept(self):
        names = [s.name for s in _extract_symbols(SAMPLE)]
        self.assertNotIn("_private_helper", names)  # 单下划线私有 → 跳过
        self.assertIn("__init__", names)            # 魔术方法 → 保留

    def test_line_number_tracked(self):
        by_name = {s.name: s for s in _extract_symbols(SAMPLE)}
        self.assertEqual(by_name["run_bash"].line, 4)  # 第 4 行（docstring 下第 3 行）


class TestBuildRepoMap(unittest.TestCase):
    def test_map_lists_files_and_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "mod.py"
            p.write_text("def foo():\n    pass\n", encoding="utf-8")
            text = build_repo_map(Path(tmp))
        self.assertIn("<repo_map>", text)
        self.assertIn("mod.py", text)
        self.assertIn("def foo", text)
        self.assertIn("</repo_map>", text)

    def test_excludes_runtime_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("def a():\n    pass\n", encoding="utf-8")
            (root / ".memory").mkdir()
            (root / ".memory" / "b.py").write_text("def b():\n    pass\n", encoding="utf-8")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "c.py").write_text("def c():\n    pass\n", encoding="utf-8")
            text = build_repo_map(root)
        self.assertIn("a.py", text)
        self.assertNotIn("b.py", text)   # .memory 被排除
        self.assertNotIn("c.py", text)   # __pycache__ 被排除

    def test_truncates_when_over_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "big.py"
            p.write_text("def f():\n    pass\n" * 50, encoding="utf-8")
            text = build_repo_map(Path(tmp), max_chars=300)
        self.assertIn("...(map truncated)...", text)
        self.assertTrue(text.endswith("</repo_map>"))  # 截断后仍闭合标签

    def test_no_python_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = build_repo_map(Path(tmp))
        self.assertEqual(text, "(no python files)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
