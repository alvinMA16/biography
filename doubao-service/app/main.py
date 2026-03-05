"""
豆包实时语音服务 - 独立微服务
处理与豆包 API 的 WebSocket 通信，隔离 websockets 12.x 依赖
"""
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse

from app.ws_handler import handle_doubao_session

app = FastAPI(title="Doubao Realtime Service", version="1.0.0")


@app.get("/health")
async def health():
    """健康检查端点"""
    return JSONResponse({"status": "healthy", "service": "doubao-realtime"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    内部 WebSocket 端点，供主 Backend 代理调用

    协议:
    1. Backend 发送 init 消息配置会话参数
    2. 双向转发音频数据
    3. Doubao Service 发送文本/事件给 Backend
    4. Backend 可发送 inject_guidance 干预指令
    """
    await handle_doubao_session(websocket)
