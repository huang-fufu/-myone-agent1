"""exceptions.py 异常分类测试：查表决定重试/提示，未知异常兜底。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from exceptions import classify


# 用与 OpenAI SDK 同名的本地类模拟真实异常（测试不依赖 openai 库）。
class RateLimitError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class BadRequestError(Exception):
    pass


class SomeWeirdError(Exception):
    pass


class TestClassify(unittest.TestCase):
    def test_rate_limit_retryable(self):
        info = classify(RateLimitError("slow down"))
        self.assertTrue(info.retry)
        self.assertIn("限流", info.hint)

    def test_auth_not_retryable(self):
        info = classify(AuthenticationError("bad key"))
        self.assertFalse(info.retry)
        self.assertIn(".env", info.hint)

    def test_context_error_marked(self):
        info = classify(BadRequestError("maximum context length exceeded"))
        self.assertTrue(info.is_context)
        self.assertFalse(info.retry)

    def test_plain_bad_request_not_context(self):
        info = classify(BadRequestError("some other bad request"))
        self.assertFalse(info.is_context)
        self.assertFalse(info.retry)

    def test_unknown_retryable_with_hint(self):
        info = classify(SomeWeirdError("boom"))
        self.assertTrue(info.retry)
        self.assertIn("未知错误", info.hint)

    def test_stdlib_connection_error_retryable(self):
        # 标准库级异常：网络波动底层可能直接抛这个，应视为可重试。
        info = classify(ConnectionError("connection refused"))
        self.assertTrue(info.retry)
        self.assertIn("网络", info.hint)

    def test_stdlib_timeout_error_retryable(self):
        info = classify(TimeoutError("timed out"))
        self.assertTrue(info.retry)
        self.assertIn("超时", info.hint)


if __name__ == "__main__":
    unittest.main(verbosity=2)