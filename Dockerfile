FROM python:3.11-slim

WORKDIR /app

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
