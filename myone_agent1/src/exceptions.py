"""异常分类：一张表决定每个异常该怎么处理（借鉴 Aider 的 exceptions.py）。

Aider 用 litellm 的所有异常建表；这里不依赖任何具体 SDK，
直接用异常类名（type(e).__name__）查表，OpenAI 等库的异常名天然匹配。
"""
from dataclasses import dataclass

# 超时类错误的提示文案相同，抽成常量避免两处重复。
_TIMEOUT_HINT = "请求超时，服务可能过载"


@dataclass(frozen=True)
class ExInfo:
    retry: bool                 # 该不该重试
    hint: str                   # 给用户看的话
    is_context: bool = False    # 是否"上下文超长"类错误（需裁剪消息后重试）


# 声明式分类表：异常名 -> 处理策略。
# 规则：key 错了重试没用（False）；限流/连接失败等服务类错误值得重试（True）。
EXCEPTIONS: dict[str, ExInfo] = {
    "RateLimitError":          ExInfo(True,  "被限流了，稍后再试或检查配额"),
    "APIConnectionError":      ExInfo(True,  "连接失败，检查网络或服务状态"),
    "APITimeoutError":         ExInfo(True,  _TIMEOUT_HINT),
    # 标准库级通用异常：某些 SDK 底层会直接抛这些，而不是包一层自家异常。
    "ConnectionError":         ExInfo(True,  "网络连接失败，检查网络后重试"),
    "TimeoutError":            ExInfo(True,  _TIMEOUT_HINT),
    "InternalServerError":     ExInfo(True,  "服务端故障，稍后重试"),
    "ServiceUnavailableError": ExInfo(True,  "服务不可用，稍后重试"),
    "AuthenticationError":     ExInfo(False, "API key 无效，请检查 .env"),
    "PermissionDeniedError":   ExInfo(False, "没有权限，请检查凭据"),
    "NotFoundError":           ExInfo(False, "请求的资源不存在"),
    "BadRequestError":         ExInfo(False, "请求参数错误"),
}


def _looks_like_context(e: Exception) -> bool:
    """上下文超长通常表现为异常消息里带这些关键词，不局限于某个异常类。"""
    s = str(e).lower()
    return any(k in s for k in ("context", "too long", "token limit"))


def classify(e: Exception) -> ExInfo:
    """决定异常处理方式。

    判断顺序很重要：
    1. 先看"是否上下文超长"——这类错误要裁剪消息后重试（is_context），
       且不写死 BadRequestError，任何异常带上超长文案都命中，兼容不同 SDK；
    2. 再查表取登记过的策略；
    3. 最后兜底：未知异常默认不重试（fail fast），避免对意外/逻辑错误
       反复退避，白白浪费时间和 token。
    """
    if _looks_like_context(e):
        return ExInfo(False, "上下文超长，已裁剪后重试", is_context=True)
    info = EXCEPTIONS.get(type(e).__name__)
    if info is not None:
        return info
    return ExInfo(False, f"未知错误（{type(e).__name__}）：{e}")
