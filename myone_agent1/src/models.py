"""模型能力元数据表。

每个模型记录：上下文窗口、最大输出、编辑格式、费用。目前两个用途：
- assemble_system_prompt 按窗口换算代码地图预算（窗口越大地图预算越多）
- 将来按 edit_format 自动选编辑模式 / 估算成本

未知模型一律返回安全默认值，绝不抛异常——查不到就按最保守配置跑。
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    name: str
    context_window: int      # 上下文窗口（token）
    max_output_tokens: int   # 单次最大输出（token）
    edit_format: str         # 适合的编辑格式："whole" / "edit" / "ask"
    cost_per_1k_in: float    # 每 1k 输入 token 费用（美元）
    cost_per_1k_out: float   # 每 1k 输出 token 费用（美元）


MODEL_REGISTRY: dict[str, ModelInfo] = {
    "gpt-4o": ModelInfo(
        "gpt-4o", context_window=128000, max_output_tokens=16384,
        edit_format="whole", cost_per_1k_in=0.005, cost_per_1k_out=0.015,
    ),
    "gpt-4o-mini": ModelInfo(
        "gpt-4o-mini", context_window=128000, max_output_tokens=16384,
        edit_format="edit", cost_per_1k_in=0.00015, cost_per_1k_out=0.0006,
    ),
    "deepseek-chat": ModelInfo(
        "deepseek-chat", context_window=64000, max_output_tokens=8192,
        edit_format="edit", cost_per_1k_in=0.00027, cost_per_1k_out=0.0011,
    ),
    "deepseek-reasoner": ModelInfo(
        "deepseek-reasoner", context_window=64000, max_output_tokens=8192,
        edit_format="edit", cost_per_1k_in=0.00055, cost_per_1k_out=0.00219,
    ),
    "claude-3-5-sonnet-20241022": ModelInfo(
        "claude-3-5-sonnet-20241022", context_window=200000, max_output_tokens=8192,
        edit_format="whole", cost_per_1k_in=0.003, cost_per_1k_out=0.015,
    ),
    "qwen-plus": ModelInfo(
        "qwen-plus", context_window=131072, max_output_tokens=8192,
        edit_format="edit", cost_per_1k_in=0.0008, cost_per_1k_out=0.002,
    ),
}

# 兜底：未知模型的安全默认（够宽的窗口 + edit 格式 + 零费用估算）。
_DEFAULT_INFO = ModelInfo(
    name="unknown", context_window=128000, max_output_tokens=8192,
    edit_format="edit", cost_per_1k_in=0.0, cost_per_1k_out=0.0,
)


def get_model_info(name: str) -> ModelInfo:
    """查表取模型能力；未知模型返回安全默认，绝不抛异常。"""
    return MODEL_REGISTRY.get(name, _DEFAULT_INFO)


def map_tokens_for(info: ModelInfo, ratio: float = 0.1) -> int:
    """代码地图预算 ≈ 上下文窗口 × ratio（默认 10%），带下限/上限。

    窗口越大，地图能塞的相关代码越多，
    但地图永远不该占满窗口，取 10% 留足对话空间。
    """
    tokens = int(info.context_window * ratio)
    return max(2000, min(tokens, 32000))


def map_chars_for(info: ModelInfo, ratio: float = 0.1) -> int:
    """字符预算 ≈ token 预算 × 4（repomap 用字符近似 token，每 token ≈ 4 字符）。"""
    return map_tokens_for(info, ratio) * 4
