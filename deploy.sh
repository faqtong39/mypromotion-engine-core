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

# 1. 拉取最新代码
echo ""
echo "[1/4] 拉取最新代码..."
git pull

# 2. 构建镜像
echo ""
echo "[2/4] 构建镜像..."
DOCKER_BUILDKIT=1 docker compose build

# 3. 启动服务
echo ""
echo "[3/4] 启动服务..."
docker compose up -d

# 4. 等待健康检查
echo ""
echo "[4/4] 等待服务就绪..."
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
