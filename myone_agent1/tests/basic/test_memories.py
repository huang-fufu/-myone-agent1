"""memories.py 长期记忆测试：读取、缺失兜底、关键词筛选。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import memories


class TestMemorySection(unittest.TestCase):
    def test_returns_string_not_exception(self):
        """无论 MEMORY.md 是否存在，都必须返回字符串，绝不能抛异常。"""
        result = memories.memory_section("__nonexistent_keyword_zzz__")
        self.assertIsInstance(result, str)
        # 找不到相关记忆时，安全兜底返回完整记忆或占位，不会崩。
        self.assertNotIn("Traceback", result)

    def test_empty_query_never_raises(self):
        """无关键词调用也必须返回字符串，绝不能抛异常。"""
        result = memories.memory_section("")
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main(verbosity=2)