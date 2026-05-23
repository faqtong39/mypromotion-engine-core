FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（curl 用于健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# 配置 pip 阿里云镜像源（国内加速）
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_TRUSTED_HOST=mirrors.aliyun.com

# 安装依赖
COPY pyproject.toml .
RUN pip install -e .[demo]

# 复制代码
COPY promotion_engine/ ./promotion_engine/
COPY demo/ ./demo/

# 创建日志目录
RUN mkdir -p /app/logs
ENV LOG_DIR=/app/logs

# 暴露端口（默认 8002，不与 mypromotion 的 8000/8001 冲突）
EXPOSE 8002

# 启动（支持环境变量 PORT）
CMD ["python", "demo/app.py"]
