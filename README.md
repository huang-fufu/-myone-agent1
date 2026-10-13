# Myone_agent1

一个自研的 **Agent 基础框架**，把 s01–s15 学到的所有机制集成到一个可运行的代码库：工具系统、Hook 事件、权限拦截、Todo 规划、Skill 技能、长期记忆、后台任务、Cron 定时、MCP 动态工具、上下文压缩。

> 学习型项目：每个机制都有最小可运行实现 + 中文注释，适合逐模块阅读。

---

## 目录结构

```
Myone_agent1/                      # 项目根目录
├── myone_agent1/                  # Agent 核心包（裸导入方案，无 __init__.py）
│   ├── main.py                    # 入口：模型 + 主循环 + CLI
│   ├── tools.py                   # 基础工具（bash/read/write/edit/glob）＋ WORKDIR 唯一来源
│   ├── permission.py              # 权限：危险命令黑名单 / 路径越界 / MCP 主机策略
│   ├── hooks.py                   # Hook 事件注册与触发（短路径拦截）
│   ├── todo_write.py              # Todo 规划工具
│   ├── skill.py                   # Skill 技能：扫描目录 + 加载技能
│   ├── memories.py                # 长期记忆：MEMORY.md 关键词筛选注入
│   ├── background_tasks.py        # 后台任务：子线程 + 通知队列
│   ├── cron_scheduler.py          # Cron 定时：注册表 + 守护扫描线程
│   ├── subagents.py               # 一次性隔离子 Agent
│   ├── mcp.py                     # MCP：模拟服务 + 动态工具装配 + system prompt 组装
│   └── context_compact.py         # 上下文压缩（分层）
├── _acceptance.py                 # 10 节自动验收脚本（临时文件，可删）
├── .env                           # 环境变量（API Key / 模型 / 项目路径）
├── requirements.txt               # 依赖清单（必装 + 可选）
└── README.md                      # 本文件
```

---

## 环境配置

```bash
# 1. 安装依赖（必装层）
pip install -r requirements.txt

# 2. 配置 .env
#    .env 已预填 DeepSeek Key 与 BASE_URL，直接可用：
#    OPENAI_API_KEY / MODEL_NAME / BASE_URL
#    若用 OpenAI 官方 API，按注释切换
```

推荐解释器：`D:\conda_envs\langchain1.2\python.exe`（已验证满足全部依赖）。

---

## 启动方式

```bash
cd Myone_agent1/myone_agent1
python main.py
```

> 注意：本项目采用**裸导入方案**（模块间平级 `from tools import ...`，无包路径），
> 所以必须在 `myone_agent1` 目录内运行 `main.py`，不能在外面 import 整个包。

---

## 各机制说明

| 机制 | 文件 | 说明 |
|---|---|---|
| 工具系统 | `tools.py` | 5 个基础工具，`@tool` 装饰后须用 `.invoke()` 调用 |
| Hook 事件 | `hooks.py` + `permission.py` | `register_hooks` 注册、`trigger_hooks` 顺序触发，首个非 None 短路 |
| 权限拦截 | `permission.py` | 危险命令黑名单、路径越界检查、`MCP_HOST_POLICY` 主机策略 |
| Todo 规划 | `todo_write.py` | Agent 用 TodoList 拆解多步任务 |
| Skill 技能 | `skill.py` | 扫描 `skills/` 目录，按需加载 SKILL.md |
| 长期记忆 | `memories.py` | `MEMORY.md` 关键词筛选 + 截断 50 行注入 |
| 后台任务 | `background_tasks.py` | 子线程跑命令，完成通知进队列由主循环注入 |
| Cron 定时 | `cron_scheduler.py` | 注册表 + 每秒扫描守护线程，到期任务弹出 |
| 子 Agent | `subagents.py` | 隔离任务，LangGraph 状态键为 `messages` |
| MCP 动态工具 | `mcp.py` | 模拟 docs/deploy 服务，连接后动态装配 `mcp__服务__工具` |
| 上下文压缩 | `context_compact.py` | 低 token 阈值时自动压缩历史 |

---

## 核心设计约定

- **裸导入 + WORKDIR 入 tools**：`WORKDIR` 只在 `tools.py` 定义，其余模块 `from tools import WORKDIR`，避免循环导入。
- **循环依赖打破**：`mcp → main`、`subagents → main` 等环均用函数内延迟 `import` 解决。
- **四段式 system prompt**：`SYSTEM_BASE + skills_catalog + memory_section + mcp_state_section`。
- **线程安全队列**：后台任务与 Cron 共用 `queue.Queue` 模式，主循环统一注入。
- **可变容器计数器**：`BG_COUNTER = [0]` / `CRON_COUNTER = [0]`，免 `global` 声明。

---

## 验收结果

10 节自动验收全部通过 ✅（工具池 11 → 13 个、后台通知、Cron 到期、权限拦截、四段式 prompt、main 可导入）。

---

## 遗留事项（非阻塞）

- `schedule_cron` 未实现（当前只有 `list_crons` / `cancel_cron`）
- `skills/` 目录不存在（有兜底逻辑）
