"""todo_write.py 待办列表测试：schema 校验、列表替换、异常兜底。

回归覆盖：参数 schema 曾是 list[str] 字符串数组，导致写入 0 项。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import todo_write


class TestTodoWrite(unittest.TestCase):
    def test_valid_todos_replaced(self):
        """合法列表：content 之外补默认 status=pending。"""
        resp = todo_write.todo_write.invoke({
            "todos": [
                {"content": "任务A", "status": "in_progress"},
                {"content": "任务B"},
            ]
        })
        self.assertIn("2 item(s)", resp)
        # 第二项缺 status → 应补默认 pending
        self.assertEqual(todo_write.TODO[1]["status"], "pending")
        # 清理，避免污染其它测试
        todo_write.TODO = []

    def test_invalid_items_filtered(self):
        """dict 里缺 content 的项应被丢弃，而不是写入脏数据。"""
        resp = todo_write.todo_write.invoke({
            "todos": [{"content": "好项"}, {"status": "in_progress"}]
        })
        self.assertIn("1 item(s)", resp)
        self.assertEqual(len(todo_write.TODO), 1)
        todo_write.TODO = []


if __name__ == "__main__":
    unittest.main(verbosity=2)