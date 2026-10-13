"""日志系统：统一配置 + 模块 logger。"""
import logging
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import logging_setup  # noqa: E402


class TestLogging(unittest.TestCase):
    def test_setup_adds_file_and_console_handlers(self):
        root = logging_setup.setup_logging()
        kinds = {type(h).__name__ for h in root.handlers}
        self.assertIn("FileHandler", kinds)
        self.assertIn("StreamHandler", kinds)

    def test_setup_is_idempotent(self):
        logging_setup.setup_logging()
        before = len(logging.getLogger().handlers)
        logging_setup.setup_logging()  # 重复调用不重复加 handler
        self.assertEqual(len(logging.getLogger().handlers), before)

    def test_get_logger_returns_module_logger(self):
        log = logging_setup.get_logger("tools")
        self.assertEqual(log.name, "tools")

    def test_warning_emitted(self):
        log = logging_setup.get_logger("probe")
        with self.assertLogs("probe", level="WARNING") as cm:
            log.warning("warning 冒烟")
        self.assertIn("warning 冒烟", cm.output[0])


if __name__ == "__main__":
    unittest.main()
