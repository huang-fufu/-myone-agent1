"""background_tasks.py 后台任务测试：异步执行 + 通知注入回调队列。

在守护线程跑一条短命命令，轮询 BACKGROUND_RESULTS 直到通知到达。
"""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from background_tasks import BACKGROUND_RESULTS, start_background_task


class TestBackgroundTask(unittest.TestCase):
    def test_echo_background_notification_arrives(self):
        """后台 echo 完成后，通知应出现并带 completed 状态。"""
        start_background_task("echo bg_hello_test")

        notification = None
        for _ in range(100):  # 最多等 5 秒
            try:
                notification = BACKGROUND_RESULTS.get_nowait()
                break
            except Exception:
                time.sleep(0.05)

        self.assertIsNotNone(notification, "后台通知未在 5 秒内到达")
        self.assertIn("<task_notification>", notification)
        self.assertIn("completed", notification)
        self.assertIn("bg_hello_test", notification)

    def test_failed_command_contains_failed(self):
        """失败命令（退出码非 0）应标为 failed，仍会通知，不崩溃。"""
        start_background_task("python -c \"import sys; sys.exit(3)\"")

        notification = None
        for _ in range(100):
            try:
                notification = BACKGROUND_RESULTS.get_nowait()
                break
            except Exception:
                time.sleep(0.05)

        self.assertIsNotNone(notification, "后台通知未在 5 秒内到达")
        self.assertIn("failed", notification)


if __name__ == "__main__":
    unittest.main(verbosity=2)