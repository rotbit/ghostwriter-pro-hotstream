# 多阶段构建 - 构建阶段
FROM mcr.microsoft.com/playwright/python:v1.53.0-noble AS builder

# 安装编译工具
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    build-essential \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制 requirements 文件
COPY requirements.txt .

# 创建虚拟环境并安装依赖
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 生产阶段 - 使用干净的 Playwright 镜像
FROM mcr.microsoft.com/playwright/python:v1.53.0-noble

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/opt/venv/bin:$PATH"

# 创建非 root 用户
RUN groupadd -r hotstream && useradd -r -g hotstream hotstream

# 设置工作目录
WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 复制应用代码
COPY . .

# 安装应用（开发模式）
RUN /opt/venv/bin/pip install -e .

# 创建必要的目录
RUN mkdir -p /app/output /app/logs /app/configs

# 设置文件权限
RUN chown -R hotstream:hotstream /app /opt/venv

# 切换到非 root 用户
USER hotstream

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import hotstream; print('OK')" || exit 1

# 暴露端口（如果需要 Web 界面）
EXPOSE 8000

# 默认命令
CMD ["python", "-m", "hotstream.cli", "start"]