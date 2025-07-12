# 使用官方 Playwright Python 镜像（已包含浏览器和系统依赖）
FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 创建非 root 用户
RUN groupadd -r hotstream && useradd -r -g hotstream hotstream

# 设置工作目录
WORKDIR /app

# 复制 requirements 文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 安装应用（开发模式）
RUN pip install -e .

# 创建必要的目录
RUN mkdir -p /app/output /app/logs /app/configs

# 设置文件权限
RUN chown -R hotstream:hotstream /app

# 切换到非 root 用户
USER hotstream

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import hotstream; print('OK')" || exit 1

# 暴露端口（如果需要 Web 界面）
EXPOSE 8000

# 默认命令
CMD ["python", "-m", "hotstream.cli", "start"]