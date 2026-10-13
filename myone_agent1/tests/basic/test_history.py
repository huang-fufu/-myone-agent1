"""会话持久化：追加写盘 + 启动恢复（照抄 Aider append_chat_history 思路）。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402

import main  # noqa: E402


class TestHistory(unittest.TestCase):
    def setUp(self):
        # 每个用例用独立临时文件，避免污染真实 .memory/history.jsonl。
        self.tmp = Path(tempfile.mkdtemp()) / "history.jsonl"

    def test_append_creates_file_with_json_line(self):
        with mock.patch.object(main, "HISTORY_FILE", self.tmp):
            main.append_history_entry("user", "你好")
        self.assertTrue(self.tmp.exists())
        entry = json.loads(self.tmp.read_text(encoding="utf-8").strip())
        self.assertEqual(entry["role"], "user")
        self.assertEqual(entry["content"], "你好")

    def test_load_history_restores_pairs(self):
        with mock.patch.object(main, "HISTORY_FILE", self.tmp):
            main.append_history_entry("user", "列出文件")
            main.append_history_entry("assistant", "好的")
            msgs = main.load_history()
        self.assertEqual(len(msgs), 2)
        self.assertIsInstance(msgs[0], HumanMessage)
        self.assertEqual(msgs[0].content, "列出文件")
        self.assertIsInstance(msgs[1], AIMessage)
        self.assertEqual(msgs[1].content, "好的")

    def test_load_history_empty_file(self):
        with mock.patch.object(main, "HISTORY_FILE", self.tmp):
            self.assertEqual(main.load_history(), [])

    def test_load_history_skips_corrupt_lines(self):
        self.tmp.parent.mkdir(parents=True, exist_ok=True)
        self.tmp.write_text('{"role": "user", "content": "好"}\nNOT-JSON\n', encoding="utf-8")
        with mock.patch.object(main, "HISTORY_FILE", self.tmp):
            msgs = main.load_history()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].content, "好")

    def test_append_skips_empty_content(self):
        with mock.patch.object(main, "HISTORY_FILE", self.tmp):
            main.append_history_entry("assistant", "")
        self.assertFalse(self.tmp.exists())  # 空内容不创建文件

    def test_load_history_keeps_recent_n(self):
        with mock.patch.object(main, "HISTORY_FILE", self.tmp):
            for i in range(25):
                main.append_history_entry("user", f"msg{i}")
            msgs = main.load_history()
        self.assertEqual(len(msgs), main.HISTORY_LIMIT)
        self.assertEqual(msgs[0].content, "msg5")   # 最早的 msg0-4 被截断
        self.assertEqual(msgs[-1].content, "msg24")  # 最新保留

    def test_append_after_failure_is_disabled(self):
        # 写失败 → HISTORY_FILE 置 None → 后续调用直接跳过不报错。
        fake = mock.Mock()
        fake.parent.mkdir = mock.Mock()
        fake.open = mock.Mock(side_effect=PermissionError("denied"))
        with mock.patch.object(main, "HISTORY_FILE", fake):
            main.append_history_entry("user", "b")
            self.assertIsNone(main.HISTORY_FILE)
            main.append_history_entry("user", "c")  # 禁用后不抛异常


if __name__ == "__main__":
    unittest.main()
