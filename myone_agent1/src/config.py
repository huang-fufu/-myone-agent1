"""统一配置：一处读取、类型校验、缺配置清晰报错。

收拢来源：
- main.py 顶部的模型名 / API key / base_url（原先散读 .env）
- permission.py 的权限表（危险命令黑名单 / MCP 主机策略）

运行时状态（如当前用的第几个 key、已连接的 MCP 客户端）不在这里，仍留在各自模块。
"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv(override=True)


def _collect_api_keys() -> list:
    """从 .env 收集所有 key：OPENAI_API_KEY + OPENAI_API_KEY_2 / _3 ..."""
    keys = []
    primary = os.getenv("OPENAI_API_KEY", "").strip()
    if primary:
        keys.append(primary)
    i = 2
    while True:
        extra = os.getenv(f"OPENAI_API_KEY_{i}", "").strip()
        if not extra:
            break
        keys.append(extra)
        i += 1
    return keys


@dataclass
class Config:
    model_name: str
    api_keys: list
    base_url: str | None
    dangerous_commands: list = field(default_factory=lambda: [
        "rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if=", "> /dev/sda",
    ])
    mcp_host_policy: dict = field(default_factory=lambda: {
        "mcp__docs__search": "allow",
        "mcp__docs__get_version": "allow",
        "mcp__deploy__status": "allow",
        "mcp__deploy__trigger": "confirm",
    })


def load_config() -> Config:
    cfg = Config(
        model_name=os.getenv("MODEL_NAME", "").strip(),
        api_keys=_collect_api_keys(),
        base_url=os.getenv("BASE_URL", "").strip() or None,
    )
    # 尽早检查，缺配置给清晰报错，别等到第一次请求模型时才炸出难懂的供应商错误。
    if not cfg.model_name:
        raise RuntimeError("请在 .env 中设置 MODEL_NAME")
    if not cfg.api_keys:
        raise RuntimeError("请在 .env 中设置 OPENAI_API_KEY")
    return cfg


CONFIG = load_config()
