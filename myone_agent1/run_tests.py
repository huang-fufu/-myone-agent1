"""一键运行 tests/basic 下所有测试文件。

用法（在 myone_agent1 目录下）：
    python run_tests.py
自动发现 tests/basic/test_*.py 并全部运行，返回非零码表示有失败。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

suite = unittest.defaultTestLoader.discover(
    start_dir=str(Path(__file__).resolve().parent / "tests" / "basic"),
    pattern="test_*.py",
)

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

sys.exit(0 if result.wasSuccessful() else 1)