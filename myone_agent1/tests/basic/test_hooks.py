"""hooks.py 事件总线测试：注册、触发、短路拦截。

回归覆盖：register_hooks 曾因 append 逻辑 bug 导致回调丢失。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import hooks


class TestHookSystem(unittest.TestCase):
    def test_register_and_trigger(self):
        calls = []
        hooks.register_hooks("TestEvent", lambda x: calls.append(x))
        result = hooks.trigger_hooks("TestEvent", "payload")
        self.assertEqual(calls, ["payload"])
        self.assertIsNone(result)

    def test_short_circuit_on_first_non_none(self):
        calls = []
        hooks.register_hooks("StopEvent", lambda x: calls.append("first") or None)
        hooks.register_hooks("StopEvent", lambda x: "blocked")
        hooks.register_hooks("StopEvent", lambda x: calls.append("third"))
        result = hooks.trigger_hooks("StopEvent", "x")
        self.assertEqual(result, "blocked")
        # 短路：第三个回调不应被执行
        self.assertNotIn("third", calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
