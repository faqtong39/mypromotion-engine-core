#!/bin/bash
#
# mypromotion-engine-core 一键部署脚本
# 用法：sudo bash deploy.sh
#

set -e

# 自动切换到项目根目录（无论从哪里调用）
cd "$(dirname "$0")"

echo "========================================"
echo "mypromotion-engine-core 部署"
echo "========================================"

# 1. 构建镜像
echo ""
echo "[1/3] 构建镜像..."
DOCKER_BUILDKIT=1 docker compose build

# 2. 启动服务
echo ""
echo "[2/3] 启动服务..."
docker compose up -d

# 3. 等待健康检查
echo ""
echo "[3/3] 等待服务就绪..."
for i in {1..30}; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' mypromotion-engine-core 2>/dev/null || echo "unknown")
    if [ "$HEALTH" = "healthy" ]; then
        echo "服务已就绪 (healthy)"
        break
    fi
    sleep 1
    if [ "$i" -eq 30 ]; then
        echo "服务启动超时，查看日志: docker compose logs -f"
        exit 1
    fi
done

IP=$(hostname -I | awk '{print $1}')

echo ""
echo "========================================"
echo "部署完成"
echo "========================================"
echo ""
echo "访问: http://${IP}:8002/demo/"
echo "日志: docker compose logs -f"
echo "状态: docker compose ps"
