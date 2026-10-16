# 更新记录

## 0.1.0 — 2026-10-15

首个可运行版本：把 s01–s15 学到的基础机制集成进一个主循环，并补齐工程化配置。

### 核心机制
- 工具系统：bash / read / write / edit / glob（`tools.py`，WORKDIR 唯一来源）
- Hook 事件：注册 + 顺序触发 + 首个非 None 短路拦截（`hooks.py`）
- 权限拦截：危险命令黑名单 / 路径越界 / MCP 主机策略（`permission.py`）
- Todo 规划：`todo_write.py`
- Skill 技能：扫描并加载 `skills/` 目录（`skill.py`）
- 长期记忆：MEMORY.md 关键词筛选注入（`memories.py`）
- 后台任务 + 通知队列（`background_tasks.py`）
- Cron 定时：注册表 + 守护扫描线程（`cron_scheduler.py`）
- 一次性隔离子 Agent（`subagents.py`）
- MCP 动态工具装配 + system prompt 组装（`mcp.py`）
- 上下文压缩（`context_compact.py`）、异常声明式分类（`exceptions.py`）
- 会话持久化（`main.py`）、API key 自动轮换、错误恢复重试

### 内核四件套
- 编辑格式：SEARCH/REPLACE 编辑块（`editblock.py`，先校验后统一落盘）
- IO 抽象：`console.py` 收口全部 input/print
- 模型元数据表：`models.py`（按模型窗口动态算 repomap 预算）
- repomap 指纹缓存：`.memory/repo_map_cache.json`（`repomap.py`）

### 工程化
- `pyproject.toml`（元数据 + 依赖统一声明）
- `.pre-commit-config.yaml`（提交前自动跑测试）
- `.github/workflows/ci.yml`（push / PR 自动跑测试）
- `LICENSE`（MIT）、`HISTORY.md`、`CONTRIBUTING.md`
