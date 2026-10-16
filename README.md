# Myone_agent1

一个自研的命令行 **AI 编程助手框架**：把工具调用、权限拦截、Todo 规划、Skill 技能、长期记忆、后台任务、Cron 定时、MCP 动态工具、上下文压缩、git 工作流等机制集成到一个可运行的代码库。

> 学习型项目：每个机制都有最小可运行实现 + 中文注释，适合逐模块阅读。

---

## 特性

- **编辑 + 语法闭环**：SEARCH/REPLACE 编辑块（先校验后统一落盘）→ 零依赖语法检查 → 错误自动喂回模型修复
- **git 保险丝**：工作区脏时拒绝编辑、编辑成功自动提交本次涉及文件、`undo_last_change` 一键回滚
- **工具调用主循环**：bash/读写/编辑/glob + 子 Agent + MCP 动态装配，API key 自动轮换 + 错误恢复重试
- **安全**：危险命令黑名单 + 用户确认 + 路径越界拦截（不引入任何第三方 Git 依赖，直接封装系统 git）
- **长期记忆**：`MEMORY.md` 索引 + 关键词筛选注入
- **斜杠命令**：`/commit` `/log` `/test` `/run` `/help`，零注册代码（`cmd_` 前缀即注册）
- **工程化**：149 个单元测试（FakeLLM 零成本）、pre-commit 自动跑测试、GitHub Actions CI

---

## 目录结构

```
Myone_agent1/                      # 项目根目录（git 仓库）
├── myone_agent1/                  # Agent 核心包（裸导入方案，无 __init__.py 依赖）
│   ├── main.py                    # 入口：模型 + 主循环 + CLI + 会话持久化
│   ├── src/
│   │   ├── tools.py               # 基础工具（bash/read/write/edit/glob）＋ WORKDIR 唯一来源
│   │   ├── editblock.py           # SEARCH/REPLACE 编辑块 + git 保险丝
│   │   ├── linter.py              # compile() 零依赖语法检查（改→查→修闭环）
│   │   ├── repomap.py             # 代码地图：正则扫描符号 + mtime 指纹缓存
│   │   ├── models.py              # 模型能力元数据表（窗口/编辑格式/费用）
│   │   ├── repo.py                # Git 薄封装（add/commit/rollback/clean）
│   │   ├── mcp.py                 # MCP 动态工具装配 + system prompt 组装 + undo_last_change
│   │   ├── permission.py          # 权限：危险命令黑名单 / 路径越界 / MCP 主机策略
│   │   ├── hooks.py               # Hook 事件注册与触发（短路径拦截）
│   │   ├── todo_write.py          # Todo 规划工具
│   │   ├── skill.py               # Skill 技能：扫描目录 + 加载技能
│   │   ├── memories.py            # 长期记忆：MEMORY.md 关键词筛选注入
│   │   ├── background_tasks.py    # 后台任务：子线程 + 通知队列
│   │   ├── cron_scheduler.py      # Cron 定时：注册表 + 守护扫描线程
│   │   ├── subagents.py           # 一次性隔离子 Agent
│   │   ├── context_compact.py     # 上下文压缩（分层）
│   │   ├── exceptions.py          # 异常声明式分类（一张表决定重试/提示）
│   │   ├── console.py             # IO 交互抽象（input/print/confirm 收口）
│   │   ├── commands.py            # 斜杠命令系统（cmd_ 前缀即注册）
│   │   ├── config.py              # 统一配置（.env 读取 + 类型校验）
│   │   └── logging_setup.py       # 日志分层（DEBUG 落盘 / INFO 控制台）
│   ├── run_tests.py               # 全量测试入口
│   └── tests/basic/               # 21 个测试文件（模块一一对应）
├── skills/                        # 技能目录（如 code-review/SKILL.md）
├── requirements.txt               # 依赖清单
├── pyproject.toml                 # 现代项目配置（元数据 + 依赖统一声明）
├── .pre-commit-config.yaml        # 提交前自动跑测试
├── .github/workflows/ci.yml       # push / PR 自动跑测试
├── LICENSE                        # MIT 开源协议
├── HISTORY.md                     # 更新记录
├── CONTRIBUTING.md                # 贡献指南
└── README.md                      # 本文件
```

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 .env（参考 .env.example）
#    MODEL_NAME / OPENAI_API_KEY / BASE_URL
#    支持 OPENAI_API_KEY_2 / _3 ... 自动轮换多把 key

# 3. 启动（注意：裸导入方案，必须在 myone_agent1 目录内运行）
cd myone_agent1
python main.py

# 4. 跑测试（FakeLLM，无需 API key）
python run_tests.py
```

---

## 工具清单

| 工具 | 说明 |
|---|---|
| `run_bash` | 执行 shell 命令（Windows 提示、120s 超时、长输出头尾截断、可后台运行） |
| `run_read` / `run_write` / `run_edit` / `run_glob` | 文件读写改 + 路径搜索（限制在 WORKDIR 内） |
| `apply_edits` | SEARCH/REPLACE 多块编辑：先校验后落盘、失败附相似行提示、git 保险丝 |
| `undo_last_change` | 一键回滚上一次 git 自动提交（`git reset --hard HEAD~1`） |
| `connect_mcp` | 连接 MCP 服务并动态装配工具 |
| `write_todos` | 多步任务规划 |
| `load_skill` / `task` / `schedule_cron` | 技能加载 / 隔离子 Agent / 定时任务 |

## 斜杠命令

| 命令 | 说明 |
|---|---|
| `/commit` | 提交当前工作区变更 |
| `/log` | 查看提交历史 |
| `/test` | 跑全量测试 |
| `/run` | 执行命令 |
| `/help` | 列出所有命令 |

---

## 核心设计约定

- **裸导入 + WORKDIR 入 tools**：`WORKDIR` 只在 `tools.py` 定义，其余模块 `from tools import WORKDIR`，避免循环导入。
- **单向依赖**：`main.py` 顶层入口向下导入子模块，子模块禁止反向 import main；环用函数内延迟 `import` 解决。
- **四段式 system prompt**：`SYSTEM_BASE + skills_catalog + memory_section + mcp_state_section`。
- **git 保险丝**：编辑前检查工作区，脏则整批拒绝；编辑落盘后自动提交；非仓库/提交失败静默降级不阻塞。
- **错误声明式查表**：所有异常类型在 `exceptions.py` 以 `ExInfo` + 字典表定义，`classify()` 查表决定重试与提示。
- **线程安全队列**：后台任务与 Cron 共用 `queue.Queue` 模式，主循环统一注入。

---

## 测试

- 全量 **149 个测试用例**全绿，覆盖主循环、工具、编辑块、git 保险丝、权限、钩子、记忆、Cron、后台任务等全部模块。
- 测试使用 FakeLLM 伪模型，**不调用真实 API，零成本**。
- pre-commit 钩子在每次 commit 时自动跑一遍测试，失败则拦截提交。
