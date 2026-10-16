# Myone_agent1 容器化
# ---------------------------------------------------------------------------
# 构建：docker build -t myone-agent1 .
# 运行（交互式 CLI，挂载 .env 提供密钥，.env 优先级高于 -e 因为 load_dotenv(override=True)）：
#   docker run --rm -it -v "%cd%\.env:/app/.env:ro" myone-agent1
# 或直接传环境变量：
#   docker run --rm -it -e MODEL_NAME=deepseek-chat -e OPENAI_API_KEY=xxx myone-agent1
# 在容器里跑测试：
#   docker run --rm -it --entrypoint python myone-agent1 /app/run_tests.py
# ---------------------------------------------------------------------------

# 项目兼容 3.12~3.14，选 3.12-slim 作为稳定体积平衡点
FROM python:3.12-slim

# agent 的 git 保险丝依赖系统 git CLI（repo.py 用 subprocess 调 git）
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先拷依赖清单并安装，利用 Docker 层缓存：依赖不变时跳过 pip install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制核心包，镜像内的布局与仓库一致：
#   /app/src      = myone_agent1/src    （全部模块 + main.py）
#   /app/skills   = myone_agent1/skills （技能目录）
#   /app/tests    = myone_agent1/tests  （供容器内跑测试）
COPY myone_agent1/src ./src
COPY myone_agent1/skills ./skills
COPY myone_agent1/run_tests.py ./run_tests.py
COPY myone_agent1/tests ./tests

# 裸导入约定：WORKDIR = Path.cwd().resolve() 即 agent 的工作区，必须是 src
WORKDIR /app/src

# 会话历史 / 记忆 / 日志统一写在 .memory，挂卷持久化
VOLUME ["/app/src/.memory"]

# 时区（可选，按需调整）
ENV TZ=Asia/Shanghai

# 入口：python main.py；.env 通过挂卷或 -e 提供
ENTRYPOINT ["python", "main.py"]
