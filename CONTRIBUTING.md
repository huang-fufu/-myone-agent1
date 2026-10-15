# 贡献指南

感谢你愿意为这个学习型项目贡献代码。以下约定能让协作更顺滑。

## 环境准备

```bash
pip install -r requirements.txt          # 必装依赖
pip install -e .[dev]                    # 可选：安装 pre-commit
```

推荐解释器：`D:\conda_envs\langchain1.2\python.exe`（已验证满足全部依赖）。

## 目录约定

- 功能模块统一放 `myone_agent1/src/`，测试文件放 `myone_agent1/tests/basic/test_<模块>.py`。
- 模块间采用**裸导入**（`from tools import WORKDIR`），包根无 `__init__.py`，
  因此必须在 `myone_agent1/` 目录内运行，不能在仓库根直接 import 整个包。
- `WORKDIR` 只在 `tools.py` 定义，其余模块统一 `from tools import WORKDIR`。
- 跨模块顶层导入易引发循环依赖，`main` 依赖的函数用函数内延迟导入。

## 测试

```bash
# 在 myone_agent1 目录下运行全部测试（唯一测试入口）
python run_tests.py
```

新增功能必须配套 `tests/basic/test_<模块>.py`，全部测试保持绿色。

## 代码风格

- 代码注释使用中文，解释"为什么"而非"是什么"。
- 不引入不必要的第三方依赖；能用标准库/内置机制解决就不用新库。
- 修改 `.py` 文件后提交前会自动触发 pre-commit 跑测试，保持绿色再提交。

## 提交

- 提交信息用中文，遵循：`动词 + 对象 + 为什么`（如 `新增 repomap 指纹缓存，避免未变更时重复扫描`）。
- 不提交 `.env`、`.memory/` 等运行时产物（已在 `.gitignore` 中）。
