#!/bin/bash

# 部署脚本 - 自动识别正式/测试环境
# 用法: ./deploy.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# 根据目录名判断环境
if [ -f docker-compose.test.yml ] && [[ "$PROJECT_DIR" == *-test ]]; then
    ENV="测试环境"
    COMPOSE="docker compose -p biography-test -f docker-compose.test.yml"
    HEALTH_PORT=8002
else
    ENV="正式环境"
    COMPOSE="docker compose"
    HEALTH_PORT=8001
fi

echo -e "${GREEN}[$ENV] [1/3] 停止旧容器...${NC}"
$COMPOSE down --remove-orphans 2>/dev/null || true

echo -e "${GREEN}[$ENV] [2/3] 构建并启动...${NC}"
$COMPOSE up -d --build

echo -e "${GREEN}[$ENV] [3/3] 等待服务就绪...${NC}"
for i in $(seq 1 30); do
    if curl -sf http://localhost:$HEALTH_PORT/health > /dev/null 2>&1; then
        echo -e "${GREEN}[$ENV] 部署完成! 服务已就绪${NC}"
        $COMPOSE ps --format "table {{.Name}}\t{{.Status}}"
        exit 0
    fi
    sleep 1
done

echo -e "${RED}[$ENV] 服务未在 30 秒内就绪，查看日志:${NC}"
$COMPOSE logs --tail=20 backend
exit 1
