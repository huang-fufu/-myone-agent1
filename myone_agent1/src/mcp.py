"""MCP 动态工具（连接发现 + 装配工具池 + system prompt 组装）。"""
import functools
import re
from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool, tool

# 循环依赖防护：mcp.py 必须独立于 main.py，唯一走 tools 取 WORKDIR/工具，
# 不再 from main import WORKDIR，从而打破 main -> mcp -> main 的循环。
from tools import (
    WORKDIR,
    run_bash,
    run_read,
    run_write,
    run_edit,
    run_glob,
)
from skill import skills_catalog, load_skill
from memories import memory_section
from subagents import task
from todo_write import todo_write
from cron_scheduler import list_crons, cancel_cron, schedule_cron
from repomap import build_repo_map
from editblock import apply_edits
from models import get_model_info, map_chars_for


def normalize_mcp_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9\-_]", "_", name)


class MCPClient:
    def __init__(self):
        self.tools = []
        self._handlers = {}

    def register(self, tool_defs, handlers):
        self.tools = list(tool_defs)
        self._handlers = dict(handlers)

    def call_tool(self, tool_name, args):
        handler = self._handlers.get(tool_name)
        if not handler:
            return f"MCP error: unknown tool '{tool_name}'"
        try:
            return str(handler(**args))
        except Exception as error:
            return f"MCP error: {type(error).__name__}: {error}"


def docs_server() -> MCPClient:
    client = MCPClient()

    def search(query: str, limit: int = 10) -> str:
        """搜索产品文档。"""
        slug = query.replace(" ", "-")
        hits = [
            f"docs/{slug}/overview",
            f"docs/{slug}/getting-started",
            f"docs/{slug}/agent-hooks",
        ][:limit]
        return "found:\n" + "\n".join(hits)

    def get_version() -> str:
        """返回文档API版本。"""
        return "docs API version 1.4.2"

    client.register(
        [
            {"name": "search", "description": "Search the product documentation."},
            {"name": "get_version", "description": "Return the documentation API version."},
        ],
        {"search": search, "get_version": get_version},
    )
    return client


def deploy_server() -> MCPClient:
    client = MCPClient()

    def status(service: str = "web") -> str:
        """返回服务的部署状态。"""
        return f"{service} service:healthy (replicas: 3/3)"

    def trigger(service: str) -> str:
        """触发服务的新部署（破坏性）。"""
        return f"triggered deployment of {service}"

    client.register(
        [
            {"name": "status", "description": "Return the deployment status of a service."},
            {"name": "trigger", "description": "Trigger a new deployment for a service (destructive)."},
        ],
        {"status": status, "trigger": trigger},
    )
    return client


MOCK_SERVERS: dict[str, Callable[[], MCPClient]] = {"docs": docs_server, "deploy": deploy_server}
mcp_clients: dict[str, MCPClient] = {}


@tool
def connect_mcp(name: str) -> str:
    """Connect to an MCP server by name ('docs' or 'deploy'), discovering its tools."""
    if name in mcp_clients:
        return f"MCP server '{name}' already connected"
    factory = MOCK_SERVERS.get(name)
    if not factory:
        return f"Unknown server '{name}'. Available: {', '.join(MOCK_SERVERS)}"
    client = factory()
    mcp_clients[name] = client
    discovered = ", ".join(
        f"mcp__{normalize_mcp_name(name)}__{normalize_mcp_name(t['name'])}"
        for t in client.tools
    )
    return f"Connected '{name}', discovered tools: {discovered}"


def _make_mcp_tool(client: MCPClient, raw_name: str, prefixed: str, description: str) -> StructuredTool:
    handler = client._handlers[raw_name]

    @functools.wraps(handler)
    def _runner(**kwargs):
        return client.call_tool(raw_name, kwargs)

    _runner.__name__ = prefixed.replace(".", "_").replace("-", "_")
    return StructuredTool.from_function(func=_runner, name=prefixed, description=description)


BASE_TOOLS = [
    run_bash, run_read, run_write, run_edit, run_glob,
    todo_write, load_skill, task,
    connect_mcp,
    list_crons, cancel_cron, schedule_cron,
    apply_edits,
]
CURRENT_TOOL_MAP: dict[str, Any] = {}


def assemble_tool_pool() -> list:
    tools = list(BASE_TOOLS)
    seen = {t.name for t in tools}
    for server_name, client in mcp_clients.items():
        safe_server = normalize_mcp_name(server_name)
        for raw in client.tools:
            safe_tool = normalize_mcp_name(raw["name"])
            prefixed = f"mcp__{safe_server}__{safe_tool}"
            if prefixed in seen:
                raise ValueError(f"MCP tool name collision after normalization: {prefixed}")
            seen.add(prefixed)
            tools.append(_make_mcp_tool(client, raw["name"], prefixed, raw["description"]))
    CURRENT_TOOL_MAP.clear()
    CURRENT_TOOL_MAP.update({t.name: t for t in tools})
    return tools


def mcp_state_section() -> str:
    if not mcp_clients:
        return "Connected MCP servers: (none)"
    return f"Connected MCP servers: {', '.join(mcp_clients)}"


SYSTEM_BASE = (
    f"you are a coding agent at {WORKDIR}. Use the provided tools to solve tasks. "
    "Plan with todo_write, load skills on demand, delegate isolated investigation with task, "
    "and schedule reminders with schedule_cron. Act, don't explain."
)


def assemble_system_prompt(query_text: str = "") -> str:
    # 按模型元数据表换算代码地图预算（窗口越大地图塞得越多），取不到配置就用默认 8000。
    max_chars, model_line = 8000, ""
    try:
        from config import load_config  # 延迟导入，避免循环依赖
        info = get_model_info(load_config().model_name)
        max_chars = map_chars_for(info)
        model_line = (
            f"Model: {info.name} (context {info.context_window}, "
            f"edit_format {info.edit_format})"
        )
    except Exception:
        pass  # 配置缺失/损坏时静默降级，绝不拖垮主流程

    parts = [
        SYSTEM_BASE,
        build_repo_map(max_chars=max_chars),  # 轻量代码地图：让模型开局看到项目结构
        skills_catalog.invoke({}),      # @tool 装饰过，须用 invoke 而非直接调用
        memory_section(query_text),     # 普通函数，直接调
        mcp_state_section(),
    ]
    if model_line:
        parts.append(model_line)
    return "\n\n".join(parts)