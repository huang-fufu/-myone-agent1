"""主循环的 FakeLLM 测试：不调真实模型，用预设响应驱动 agent 循环。

思路抄自 Aider 的 tests/basic/test_main.py：
- FakeModel 替换 main.MODEL：bind_tools 原样返回自己，invoke 依次吐出预设 AIMessage
- 只测框架逻辑：工具调用解析、工具执行、结果回流、循环终止
- 全程不碰真实 API，不花一分钱

运行方式（必须在 myone_agent1 目录下）：
    python tests/test_agent_loop.py
"""
import sys
import tempfile
import unittest
from pathlib import Path

# 让 `import main` 可用：测试文件在 myone_agent1/tests/ 里，
# 上级目录 myone_agent1 才是包根，需手动加进 import 路径。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from tools import WORKDIR

import main


class FakeModel:
    """伪模型：按顺序吐预设响应，永不发真实请求。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def bind_tools(self, tools):
        # 真实模型这里会绑定工具 schema；伪模型直接返回自己，让 invoke 可用。
        self.last_tools = tools
        return self

    def invoke(self, messages):
        self.calls.append(messages)
        if self.responses:
            return self.responses.pop(0)
        return AIMessage(content="（测试结束）")


def make_tool_call(tool_call_id, name, args):
    """构造一条带工具调用的 AIMessage。"""
    return AIMessage(
        content="",
        tool_calls=[{"id": tool_call_id, "name": name, "args": args}],
    )


class TestExecuteToolCalls(unittest.TestCase):
    """最小粒度：单条 AIMessage 里的工具调用是否能被正确执行。"""

    def setUp(self):
        self.original_model = main.MODEL

    def tearDown(self):
        main.MODEL = self.original_model

    def test_glob_tool_runs_and_returns_result(self):
        """模型想用 run_glob，工具应真实执行并返回结果消息。"""
        outputs = main.execute_tool_calls(
            make_tool_call("call-1", "run_glob", {"pattern": "src/*.py"})
        )
        self.assertEqual(len(outputs), 1)
        self.assertIsInstance(outputs[0], ToolMessage)
        self.assertIn("tools.py", outputs[0].content)

    def test_unknown_tool_reports_error(self):
        """模型调了不存在的工具，应返回 unknown tool 错误而不是崩溃。"""
        outputs = main.execute_tool_calls(
            make_tool_call("call-9", "not_a_real_tool", {})
        )
        self.assertEqual(len(outputs), 1)
        self.assertIn("unknown tool", outputs[0].content)

    def test_write_broken_py_appends_linter_fix(self):
        """linter 闭环：写完语法错误的 .py，应追加一条修复指令消息给模型。"""
        with tempfile.TemporaryDirectory(dir=WORKDIR) as tmp:
            path = str(Path(tmp) / "bad.py")
            outputs = main.execute_tool_calls(
                make_tool_call("call-3", "run_write", {"path": path, "content": "def broken(:\n    pass\n"})
            )
        self.assertEqual(len(outputs), 2)  # 写入结果 + linter 指令
        linter_msg = outputs[1]
        self.assertEqual(linter_msg.name, "linter")
        self.assertIn("Fix any errors below", linter_msg.content)
        self.assertIn("SyntaxError", linter_msg.content)

    def test_write_clean_py_no_linter(self):
        """语法正确的 .py 不该触发 linter 追加消息。"""
        with tempfile.TemporaryDirectory(dir=WORKDIR) as tmp:
            path = str(Path(tmp) / "ok.py")
            outputs = main.execute_tool_calls(
                make_tool_call("call-4", "run_write", {"path": path, "content": "print('ok')\n"})
            )
        self.assertEqual(len(outputs), 1)
        self.assertNotEqual(outputs[0].name, "linter")

    def test_edit_broken_py_appends_linter_fix(self):
        """run_edit 改坏 .py 同样触发 linter 闭环。"""
        with tempfile.TemporaryDirectory(dir=WORKDIR) as tmp:
            path = str(Path(tmp) / "mod.py")
            main.execute_tool_calls(
                make_tool_call("call-5", "run_write", {"path": path, "content": "def ok():\n    pass\n"})
            )
            outputs = main.execute_tool_calls(
                make_tool_call("call-6", "run_edit", {"path": path, "old_text": "def ok():", "new_text": "def broken(:"})
            )
        self.assertEqual(len(outputs), 2)
        self.assertEqual(outputs[1].name, "linter")
        self.assertIn("Fix any errors below", outputs[1].content)

    def test_write_non_py_no_linter(self):
        """非 .py 文件（如 md/json）不该触发 linter。"""
        with tempfile.TemporaryDirectory(dir=WORKDIR) as tmp:
            path = str(Path(tmp) / "note.txt")
            outputs = main.execute_tool_calls(
                make_tool_call("call-7", "run_write", {"path": path, "content": "随便写点啥\n"})
            )
        self.assertEqual(len(outputs), 1)
        self.assertNotEqual(outputs[0].name, "linter")


class TestAgentLoopWithFakeLLM(unittest.TestCase):
    """完整一轮对话：验证模型→工具→模型→结束的闭环。"""

    def setUp(self):
        self.original_model = main.MODEL

    def tearDown(self):
        main.MODEL = self.original_model

    def test_full_round_trip(self):
        fake = FakeModel([
            # 第 1 次 invoke：要求执行 run_glob
            make_tool_call("call-2", "run_glob", {"pattern": "src/*.py"}),
            # 第 2 次 invoke：不再要工具，直接给最终回答
            AIMessage(content="找到文件了。"),
        ])
        main.MODEL = fake

        history = [HumanMessage(content="列出项目里的 py 文件")]
        main.agent_loop(history)

        # 断言 1：工具执行结果回到了消息流
        tool_msgs = [m for m in history if isinstance(m, ToolMessage)]
        self.assertTrue(tool_msgs, "工具结果没有注入消息流")
        # 断言 2：模型被调了两次（工具前 + 工具后）
        self.assertEqual(len(fake.calls), 2)
        # 断言 3：循环正确终止在模型的最终回答上
        self.assertIsInstance(history[-1], AIMessage)
        self.assertEqual(history[-1].content, "找到文件了。")


if __name__ == "__main__":
    unittest.main(verbosity=2)
