"""异常分类：一张表决定每个异常该怎么处理（借鉴 Aider 的 exceptions.py）。

Aider 用 litellm 的所有异常建表；这里不依赖任何具体 SDK，
直接用异常类名（type(e).__name__）查表，OpenAI 等库的异常名天然匹配。
"""
from dataclasses import dataclass


@dataclass
class ExInfo:
    retry: bool                 # 该不该重试
    hint: str                   # 给用户看的话
    is_context: bool = False    # 是否"上下文超长"类错误（需裁剪消息后重试）


# 声明式分类表：异常名 -> 处理策略。
# 规则：key 错了重试没用（False）；限流/连接失败等服务类错误值得重试（True）。
EXCEPTIONS = {
    "RateLimitError":          ExInfo(True,  "被限流了，稍后再试或检查配额"),
    "APIConnectionError":      ExInfo(True,  "连接失败，检查网络或服务状态"),
    "APITimeoutError":         ExInfo(True,  "请求超时，服务可能过载"),
    "InternalServerError":     ExInfo(True,  "服务端故障，稍后重试"),
    "ServiceUnavailableError": ExInfo(True,  "服务不可用，稍后重试"),
    "AuthenticationError":     ExInfo(False, "API key 无效，请检查 .env"),
    "PermissionDeniedError":   ExInfo(False, "没有权限，请检查凭据"),
    "NotFoundError":           ExInfo(False, "请求的资源不存在"),
    "BadRequestError":         ExInfo(False, "请求参数错误"),
}


def _looks_like_context(e: Exception) -> bool:
    """OpenAI 的上下文超长通常表现为 BadRequestError + 特定文案。"""
    s = str(e).lower()
    return any(k in s for k in ("context", "too long", "token limit"))


def classify(e: Exception) -> ExInfo:
    """查表决定异常处理方式；未知异常默认可重试，但提示要透明。"""
    name = type(e).__name__
    info = EXCEPTIONS.get(name)
    if info is not None:
        # 特判：BadRequestError 若是上下文超长，交给裁剪逻辑而不是普通重试。
        if name == "BadRequestError" and _looks_like_context(e):
            return ExInfo(False, "上下文超长，已裁剪后重试", is_context=True)
        return info
    return ExInfo(True, f"未知错误（{name}）：{e}")
