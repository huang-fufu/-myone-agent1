"""日志系统：统一日志配置，控制台保留关键信息，细节落盘 .memory/agent.log。

用法：各模块 `from logging_setup import get_logger; log = get_logger(__name__)`
然后 log.info(...) / log.warning(...) / log.error(...)。
等级：DEBUG 只进文件，INFO 以上控制台+文件。
"""
import logging
import sys

from tools import WORKDIR

_configured = False


def setup_logging(level: int = logging.WARNING) -> logging.Logger:
    """配置全局日志（幂等），返回根 logger。

    level 是控制台阈值：默认 WARNING，挡住第三方库（httpx2/langsmith 等）
    的 INFO 刷屏；要看到自有模块的 info 级日志时传 logging.INFO。
    """
    global _configured
    if _configured:
        return logging.getLogger()

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt_file = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    fmt_console = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")

    # 文件 handler：DEBUG 全落盘，方便排查（不降噪，第三方也保留）。
    log_dir = WORKDIR / ".memory"
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / "agent.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt_file)
    root.addHandler(fh)

    # 控制台 handler：默认 WARNING 以上，规避 httpx2 等请求日志刷屏。
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(level)
    sh.setFormatter(fmt_console)
    root.addHandler(sh)

    # 第三方库日志降噪：只留 WARNING 以上，避免 agent.log 被 DEBUG 刷屏。
    for name in (
        "langsmith", "langchain", "langchain_core", "langchain_openai",
        "openai", "urllib3", "httpx", "httpcore", "dotenv",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True
    return root


def get_logger(name: str) -> logging.Logger:
    """取一个模块级 logger（懒初始化全局配置）。"""
    setup_logging()
    return logging.getLogger(name)