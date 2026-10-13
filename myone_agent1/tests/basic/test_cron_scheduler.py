"""cron_scheduler.py 定时任务测试：注册 / 列出的闭环。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from cron_scheduler import cancel_cron, list_crons, schedule_cron


class TestCronScheduler(unittest.TestCase):
    def test_schedule_and_list_and_cancel(self):
        # schedule_cron 是 @tool 装饰的 StructuredTool，必须 .invoke() 调用。
        resp = schedule_cron.invoke({"prompt": "test reminder", "seconds": 3600})
        cid = resp.strip()
        try:
            self.assertTrue(cid)
            listed = list_crons.invoke({})
            self.assertIn("test reminder", listed)
        finally:
            cancel_cron.invoke({"job_id": int(cid.split("#")[1].split()[0])})


if __name__ == "__main__":
    unittest.main(verbosity=2)