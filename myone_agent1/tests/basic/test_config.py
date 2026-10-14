"""config.py + main.py 的配置管理 / API key 轮换测试。

覆盖：
- _collect_api_keys 多 key 收集（主 key + _2/_3，遇到空位即停）
- load_config 缺配置（缺 MODEL_NAME / 缺 key）清晰报错
- Config dataclass 默认权限表（dangerous / MCP 策略）
- permission 从 CONFIG 取表（收拢后无硬编码重复）
- main.rotate_api_key 多 key 切换 / 单 key 无操作 / 循环回绕

注意：config.py 模块级执行 CONFIG = load_config()，import 时若环境缺配置会
直接 raise。这里在 import 前 setdefault 兜底，保证无 .env 的 CI 环境也能跑。
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

# import 前的兜底：缺 .env 的环境也能加载模块级 CONFIG。
os.environ.setdefault("MODEL_NAME", "test-model")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from config import Config, CONFIG, _collect_api_keys, load_config


class TestCollectApiKeys(unittest.TestCase):
    def test_primary_only(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "k1"}, clear=True):
            self.assertEqual(_collect_api_keys(), ["k1"])

    def test_multiple_keys_collected_in_order(self):
        with mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "k1", "OPENAI_API_KEY_2": "k2", "OPENAI_API_KEY_3": "k3"},
            clear=True,
        ):
            self.assertEqual(_collect_api_keys(), ["k1", "k2", "k3"])

    def test_gap_stops_collection(self):
        """编号有空位（_3 存在但 _2 缺失）→ 视为后面的 key 都不可用。"""
        with mock.patch.dict(
            os.environ, {"OPENAI_API_KEY": "k1", "OPENAI_API_KEY_3": "k3"}, clear=True
        ):
            self.assertEqual(_collect_api_keys(), ["k1"])


class TestLoadConfig(unittest.TestCase):
    def test_missing_model_name_raises(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "k1"}, clear=True):
            with self.assertRaises(RuntimeError):
                load_config()

    def test_missing_api_key_raises(self):
        with mock.patch.dict(os.environ, {"MODEL_NAME": "m"}, clear=True):
            with self.assertRaises(RuntimeError):
                load_config()

    def test_full_config_loaded(self):
        with mock.patch.dict(
            os.environ,
            {"MODEL_NAME": "m", "OPENAI_API_KEY": "k1", "BASE_URL": "http://x"},
            clear=True,
        ):
            cfg = load_config()
        self.assertEqual(cfg.model_name, "m")
        self.assertEqual(cfg.api_keys, ["k1"])
        self.assertEqual(cfg.base_url, "http://x")


class TestConfigDefaults(unittest.TestCase):
    def test_dangerous_and_mcp_defaults(self):
        """权限表默认值：危险命令黑名单 + MCP 主机策略。"""
        cfg = Config(model_name="m", api_keys=["k"], base_url=None)
        self.assertIn("rm -rf /", cfg.dangerous_commands)
        self.assertEqual(cfg.mcp_host_policy["mcp__deploy__trigger"], "confirm")


class TestPermissionUsesConfig(unittest.TestCase):
    def test_tables_read_from_config(self):
        """permission 的权限表应来自 CONFIG，而非另写一份硬编码。"""
        import permission
        self.assertEqual(permission.dangerous, CONFIG.dangerous_commands)
        self.assertEqual(permission.MCP_HOST_POLICY, CONFIG.mcp_host_policy)


class TestApiKeyRotation(unittest.TestCase):
    """main.rotate_api_key 的切换逻辑。"""

    def setUp(self):
        import main
        self.orig_index = main.API_KEY_INDEX[0]
        self.orig_model = main.MODEL

    def tearDown(self):
        import main
        main.API_KEY_INDEX[0] = self.orig_index
        main.MODEL = self.orig_model

    def test_rotate_switches_to_next_key(self):
        import main
        with mock.patch.object(main, "CONFIG") as cfg:
            cfg.api_keys = ["k1", "k2"]
            with mock.patch.object(main, "build_chat_model", return_value="model-2"):
                main.rotate_api_key()
        self.assertEqual(main.API_KEY_INDEX[0], 1)
        self.assertEqual(main.MODEL, "model-2")

    def test_rotate_noop_with_single_key(self):
        import main
        with mock.patch.object(main, "CONFIG") as cfg:
            cfg.api_keys = ["only"]
            with mock.patch.object(main, "build_chat_model") as build:
                main.rotate_api_key()
        self.assertEqual(main.API_KEY_INDEX[0], 0)
        build.assert_not_called()  # 单 key 不该重建 MODEL

    def test_rotate_wraps_around(self):
        import main
        main.API_KEY_INDEX[0] = 2  # 假设已切到第 3 个
        with mock.patch.object(main, "CONFIG") as cfg:
            cfg.api_keys = ["k1", "k2", "k3"]
            with mock.patch.object(main, "build_chat_model"):
                main.rotate_api_key()
        self.assertEqual(main.API_KEY_INDEX[0], 0)  # 回绕到第 1 个


if __name__ == "__main__":
    unittest.main(verbosity=2)
