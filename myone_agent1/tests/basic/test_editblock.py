"""editblock.py SEARCH/REPLACE 编辑格式的测试。

回归覆盖：
- parse_edits：单块/多块/带 markdown 围栏/残缺格式
- apply_edits_core：成功替换、中文替换、新建文件、多文件
- 安全校验：SEARCH 未找到 / 不唯一 / 多块部分失败 → 整批拒绝不落盘
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from editblock import apply_edits_core, parse_edits
from tools import WORKDIR


class TestParseEdits(unittest.TestCase):
    def test_single_block(self):
        text = """<path>src/tools.py</path>
<search>
old_text
</search>
<replace>
new_text
</replace>"""
        edits, errors = parse_edits(text)
        self.assertEqual(errors, [])
        self.assertEqual(edits[0]["path"], "src/tools.py")
        self.assertEqual(edits[0]["search"], "old_text")
        self.assertEqual(edits[0]["replace"], "new_text")

    def test_multiple_blocks(self):
        text = (
            "<path>a.py</path><search>old1</search><replace>new1</replace>\n"
            "<path>b.py</path><search>old2</search><replace>new2</replace>"
        )
        edits, errors = parse_edits(text)
        self.assertEqual(errors, [])
        self.assertEqual(len(edits), 2)
        self.assertEqual(edits[1]["path"], "b.py")

    def test_ignores_markdown_fence(self):
        text = """```python
<path>a.py</path>
<search>
old
</search>
<replace>
new
</replace>
```"""
        edits, errors = parse_edits(text)
        self.assertEqual(errors, [])
        self.assertEqual(edits[0]["search"], "old")

    def test_malformed_block_reports_error(self):
        text = "<path>a.py</path><search>old</search>"  # 缺 <replace>
        edits, errors = parse_edits(text)
        self.assertEqual(edits, [])
        self.assertIn("未找到", errors[0])


class TestApplyEdits(unittest.TestCase):
    def _tmp(self):
        return tempfile.TemporaryDirectory(dir=WORKDIR)

    def test_successful_replace(self):
        with self._tmp() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
            report = apply_edits_core(
                [{"path": "a.py", "search": "return 1", "replace": "return 42"}], root
            )
            self.assertIn("applied successfully", report)
            self.assertIn("return 42", (root / "a.py").read_text(encoding="utf-8"))

    def test_chinese_replace(self):
        with self._tmp() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("print('你好')\n", encoding="utf-8")
            report = apply_edits_core(
                [{"path": "a.py", "search": "你好", "replace": "世界"}], root
            )
            self.assertIn("applied successfully", report)
            self.assertIn("世界", (root / "a.py").read_text(encoding="utf-8"))

    def test_multiple_files(self):
        with self._tmp() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("AAA\n", encoding="utf-8")
            (root / "b.py").write_text("BBB\n", encoding="utf-8")
            report = apply_edits_core(
                [
                    {"path": "a.py", "search": "AAA", "replace": "aaa"},
                    {"path": "b.py", "search": "BBB", "replace": "bbb"},
                ],
                root,
            )
            self.assertIn("2 SEARCH/REPLACE blocks applied", report)
            self.assertIn("aaa", (root / "a.py").read_text(encoding="utf-8"))
            self.assertIn("bbb", (root / "b.py").read_text(encoding="utf-8"))

    def test_create_new_file(self):
        with self._tmp() as tmp:
            root = Path(tmp)
            report = apply_edits_core(
                [{"path": "new.py", "search": "", "replace": "x = 1\n"}], root
            )
            self.assertIn("applied successfully", report)
            self.assertIn("x = 1", (root / "new.py").read_text(encoding="utf-8"))

    def test_search_not_found_does_not_touch_file(self):
        with self._tmp() as tmp:
            root = Path(tmp)
            p = root / "a.py"
            p.write_text("original\n", encoding="utf-8")
            report = apply_edits_core(
                [{"path": "a.py", "search": "nothing here", "replace": "x"}], root
            )
            self.assertIn("failed to match", report)
            self.assertIn("SEARCH 片段未找到", report)
            self.assertEqual(p.read_text(encoding="utf-8"), "original\n")  # 文件未动

    def test_search_not_unique_rejected(self):
        with self._tmp() as tmp:
            root = Path(tmp)
            p = root / "a.py"
            p.write_text("dup\ndup\n", encoding="utf-8")
            report = apply_edits_core(
                [{"path": "a.py", "search": "dup", "replace": "x"}], root
            )
            self.assertIn("匹配 2 处", report)
            self.assertEqual(p.read_text(encoding="utf-8"), "dup\ndup\n")  # 文件未动

    def test_partial_failure_aborts_all(self):
        with self._tmp() as tmp:
            root = Path(tmp)
            p = root / "a.py"
            p.write_text("keep\n", encoding="utf-8")
            report = apply_edits_core(
                [
                    {"path": "a.py", "search": "keep", "replace": "changed"},  # 会成功
                    {"path": "b.py", "search": "missing", "replace": "x"},      # 会失败
                ],
                root,
            )
            self.assertIn("1 SEARCH/REPLACE block failed to match", report)
            self.assertEqual(p.read_text(encoding="utf-8"), "keep\n")  # 原子性：未落盘


if __name__ == "__main__":
    unittest.main(verbosity=2)
