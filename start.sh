#!/bin/bash

# 回忆录项目启动脚本

# 项目目录（脚本所在目录）
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
WEB_DIR="$PROJECT_DIR/web"

# PID 和日志文件
BACKEND_PID="$BACKEND_DIR/app.pid"
BACKEND_LOG="$BACKEND_DIR/app.log"
WEB_PID="$WEB_DIR/web.pid"
WEB_LOG="$WEB_DIR/web.log"

# 端口
BACKEND_PORT=8001
WEB_PORT=8080

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

start_backend() {
    if [ -f "$BACKEND_PID" ] && kill -0 $(cat "$BACKEND_PID") 2>/dev/null; then
        echo -e "${YELLOW}后端已在运行中 (PID: $(cat $BACKEND_PID))${NC}"
        return 1
    fi

    echo -e "${GREEN}启动后端服务...${NC}"
    cd "$BACKEND_DIR"
    source venv/bin/activate
    nohup python -m uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID"
    sleep 2

    if kill -0 $(cat "$BACKEND_PID") 2>/dev/null; then
        echo -e "${GREEN}后端已启动 (PID: $(cat $BACKEND_PID), 端口: $BACKEND_PORT)${NC}"
    else
        echo -e "${RED}后端启动失败，请查看日志: $BACKEND_LOG${NC}"
        rm -f "$BACKEND_PID"
        return 1
    fi
}

start_web() {
    if [ -f "$WEB_PID" ] && kill -0 $(cat "$WEB_PID") 2>/dev/null; then
        echo -e "${YELLOW}前端已在运行中 (PID: $(cat $WEB_PID))${NC}"
        return 1
    fi

    echo -e "${GREEN}启动前端服务...${NC}"
    cd "$WEB_DIR"
    nohup python -m http.server $WEB_PORT > "$WEB_LOG" 2>&1 &
    echo $! > "$WEB_PID"
    sleep 1

    if kill -0 $(cat "$WEB_PID") 2>/dev/null; then
        echo -e "${GREEN}前端已启动 (PID: $(cat $WEB_PID), 端口: $WEB_PORT)${NC}"
    else
        echo -e "${RED}前端启动失败，请查看日志: $WEB_LOG${NC}"
        rm -f "$WEB_PID"
        return 1
    fi
}

stop_backend() {
    if [ ! -f "$BACKEND_PID" ]; then
        echo -e "${YELLOW}后端未运行${NC}"
        return 1
    fi

    PID=$(cat "$BACKEND_PID")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${GREEN}停止后端 (PID: $PID)...${NC}"
        kill "$PID"
        sleep 2
        kill -0 "$PID" 2>/dev/null && kill -9 "$PID"
        echo -e "${GREEN}后端已停止${NC}"
    fi
    rm -f "$BACKEND_PID"
}

stop_web() {
    if [ ! -f "$WEB_PID" ]; then
        echo -e "${YELLOW}前端未运行${NC}"
        return 1
    fi

    PID=$(cat "$WEB_PID")
    if kill -0 "$PID" 2>/dev/null; then
        echo -e "${GREEN}停止前端 (PID: $PID)...${NC}"
        kill "$PID"
        sleep 1
        kill -0 "$PID" 2>/dev/null && kill -9 "$PID"
        echo -e "${GREEN}前端已停止${NC}"
    fi
    rm -f "$WEB_PID"
}

start() {
    start_backend
    start_web
    echo ""
    echo -e "${GREEN}访问地址: http://localhost:$WEB_PORT${NC}"
}

stop() {
    stop_backend
    stop_web
}

restart() {
    stop
    sleep 1
    start
}

status() {
    echo "=== 服务状态 ==="
    if [ -f "$BACKEND_PID" ] && kill -0 $(cat "$BACKEND_PID") 2>/dev/null; then
        echo -e "后端: ${GREEN}运行中${NC} (PID: $(cat $BACKEND_PID), 端口: $BACKEND_PORT)"
    else
        echo -e "后端: ${RED}未运行${NC}"
        rm -f "$BACKEND_PID" 2>/dev/null
    fi

    if [ -f "$WEB_PID" ] && kill -0 $(cat "$WEB_PID") 2>/dev/null; then
        echo -e "前端: ${GREEN}运行中${NC} (PID: $(cat $WEB_PID), 端口: $WEB_PORT)"
    else
        echo -e "前端: ${RED}未运行${NC}"
        rm -f "$WEB_PID" 2>/dev/null
    fi
}

logs() {
    echo "=== 后端日志 ==="
    tail -20 "$BACKEND_LOG" 2>/dev/null || echo "无日志"
    echo ""
    echo "=== 前端日志 ==="
    tail -10 "$WEB_LOG" 2>/dev/null || echo "无日志"
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "  start   - 启动前端和后端"
        echo "  stop    - 停止所有服务"
        echo "  restart - 重启所有服务"
        echo "  status  - 查看状态"
        echo "  logs    - 查看日志"
        exit 1
        ;;
esac
