"""context_compact.py 上下文压缩测试：单条截断、累计预算、非工具消息保留。

覆盖 compact_messages 的三个核心行为：
1. 非 ToolMessage 原样保留、不改动对象
2. 单条工具结果超过 4000 字符 -> 截断 + (snipped) 标记
3. 累计工具结果超过 20000 字符 -> 进一步压缩 + (further compacted) 标记
以及截断后 tool_call_id / name 元数据仍保留、原列表不被修改。

运行方式（在 myone_agent1 目录下）：
    python tests/basic/test_context_compact.py
"""
import sys
import unittest
from pathlib import Path

# 项目是裸导入方案：把 src/ 加进 import 路径，才能 `import context_compact`。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

import context_compact


class TestCompactMessages(unittest.TestCase):
    def _tool(self, content, tool_call_id="t1", name="run_read"):
        return ToolMessage(content=content, tool_call_id=tool_call_id, name=name)

    def test_non_tool_messages_preserved(self):
        """非 ToolMessage（人类/AI 消息）必须原样保留，不重建、不丢弃。"""
        human = HumanMessage(content="hi")
        ai = AIMessage(content="ok")
        out = context_compact.compact_messages([human, ai])
        self.assertEqual(len(out), 2)
        self.assertIs(out[0], human)  # 是同一个对象，未被重建
        self.assertIs(out[1], ai)

    def test_short_tool_message_unchanged(self):
        """短工具结果（未超单条 4000 上限）应原样返回。"""
        msg = self._tool("short result", tool_call_id="c1")
        out = context_compact.compact_messages([msg])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].content, "short result")

    def test_single_tool_message_truncated(self):
        """单条工具结果超过 4000 字符 -> 截断并加 (snipped) 标记。"""
        big = "x" * (context_compact.MAX_SINGLE_TOOL_CHARS + 100)
        msg = self._tool(big, tool_call_id="c2", name="run_read")
        out = context_compact.compact_messages([msg])
        self.assertEqual(len(out), 1)
        self.assertIsInstance(out[0], ToolMessage)
        content = out[0].content
        self.assertTrue(content.endswith("...(snipped)"))
        # 截断长度 = 上限 + 标记文本长度，不多不少
        self.assertEqual(
            len(content),
            context_compact.MAX_SINGLE_TOOL_CHARS + len("\n...(snipped)"),
        )

    def test_cumulative_budget_truncated(self):
        """累计工具结果超过 20000 -> 触发进一步压缩 (further compacted)。"""
        # 每条 4000 字符，前 5 条累计恰好 20000（不超），第 6 条累加后 24000 超预算。
        msgs = [self._tool("y" * 4000, tool_call_id=f"c{i}") for i in range(6)]
        out = context_compact.compact_messages(msgs)
        last = out[-1]
        self.assertTrue(last.content.endswith("...(further compacted)"))
        self.assertEqual(len(last.content), 500 + len("\n...(further compacted)"))

    def test_metadata_preserved_after_truncation(self):
        """截断后 tool_call_id 与 name 必须保留，供后续关联。"""
        msg = self._tool("x" * 5000, tool_call_id="call-42", name="run_bash")
        out = context_compact.compact_messages([msg])
        self.assertEqual(out[0].tool_call_id, "call-42")
        self.assertEqual(out[0].name, "run_bash")

    def test_original_list_not_mutated(self):
        """压缩应返回新列表，不修改传入的原列表内容。"""
        msgs = [self._tool("short")]
        context_compact.compact_messages(msgs)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].content, "short")


if __name__ == "__main__":
    unittest.main(verbosity=2)
