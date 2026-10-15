"""models.py 模型能力元数据表的测试。

回归覆盖：
- 已知模型查表返回正确能力
- 未知模型返回安全默认、绝不抛异常
- map_tokens_for 按窗口换算并带下限/上限
- map_chars_for 是 token 预算的 4 倍（repomap 字符近似）
- 注册表每个模型都有编辑格式
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from models import MODEL_REGISTRY, get_model_info, map_chars_for, map_tokens_for


class TestModelRegistry(unittest.TestCase):
    def test_known_model_lookup(self):
        info = get_model_info("gpt-4o")
        self.assertEqual(info.context_window, 128000)
        self.assertEqual(info.max_output_tokens, 16384)

    def test_unknown_model_falls_back_safely(self):
        info = get_model_info("no-such-model-xyz")  # 不应抛异常
        self.assertEqual(info.name, "unknown")
        self.assertGreater(info.context_window, 0)

    def test_registry_has_common_models(self):
        for name in ("gpt-4o", "gpt-4o-mini", "deepseek-chat", "claude-3-5-sonnet-20241022"):
            self.assertIn(name, MODEL_REGISTRY)

    def test_every_model_has_edit_format(self):
        for name, info in MODEL_REGISTRY.items():
            self.assertIn(info.edit_format, ("whole", "edit", "ask"), name)


class TestMapBudget(unittest.TestCase):
    def test_map_tokens_ratio(self):
        info = get_model_info("gpt-4o")
        self.assertEqual(map_tokens_for(info), 12800)  # 128000 × 10%

    def test_map_tokens_lower_bound(self):
        info = get_model_info("deepseek-chat")  # 64000 × 10% = 6400，正常值
        small = type(info)("t", context_window=1000, max_output_tokens=256,
                          edit_format="edit", cost_per_1k_in=0, cost_per_1k_out=0)
        self.assertEqual(map_tokens_for(small), 2000)  # 下限兜底

    def test_map_tokens_upper_bound(self):
        huge = type(get_model_info("gpt-4o"))(
            "huge", context_window=1_000_000, max_output_tokens=8192,
            edit_format="edit", cost_per_1k_in=0, cost_per_1k_out=0,
        )
        self.assertEqual(map_tokens_for(huge), 32000)  # 上限兜底

    def test_map_chars_is_4x_tokens(self):
        info = get_model_info("deepseek-chat")
        self.assertEqual(map_chars_for(info), map_tokens_for(info) * 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
