"""
实时对话 WebSocket API
前端通过 WebSocket 连接，发送音频，接收音频和文本回复
"""
import asyncio
import json
import base64
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.doubao_realtime import DoubaoRealtimeClient

router = APIRouter()


@router.websocket("/dialog")
async def realtime_dialog(websocket: WebSocket):
    """
    实时对话 WebSocket 端点

    前端发送消息格式:
    - {"type": "audio", "data": "<base64 encoded pcm audio>"}
    - {"type": "start"}
    - {"type": "stop"}

    后端发送消息格式:
    - {"type": "audio", "data": "<base64 encoded pcm audio>"}
    - {"type": "text", "text_type": "asr|response", "content": "..."}
    - {"type": "event", "event": <event_code>, "payload": {...}}
    - {"type": "status", "status": "connected|disconnected|error", "message": "..."}
    """
    await websocket.accept()

    client = None
    receive_task = None

    async def on_audio(audio_data: bytes):
        """收到音频回复"""
        try:
            await websocket.send_json({
                "type": "audio",
                "data": base64.b64encode(audio_data).decode()
            })
        except Exception as e:
            print(f"发送音频失败: {e}")

    async def on_text(text_type: str, content: str):
        """收到文本"""
        try:
            await websocket.send_json({
                "type": "text",
                "text_type": text_type,
                "content": content
            })
        except Exception as e:
            print(f"发送文本失败: {e}")

    async def on_event(event: int, payload: dict):
        """收到事件"""
        try:
            await websocket.send_json({
                "type": "event",
                "event": event,
                "payload": payload if isinstance(payload, dict) else {}
            })
        except Exception as e:
            print(f"发送事件失败: {e}")

    try:
        # 创建豆包客户端
        client = DoubaoRealtimeClient(
            on_audio=lambda data: asyncio.create_task(on_audio(data)),
            on_text=lambda t, c: asyncio.create_task(on_text(t, c)),
            on_event=lambda e, p: asyncio.create_task(on_event(e, p)),
        )

        # 连接到豆包
        connected = await client.connect()
        if not connected:
            await websocket.send_json({
                "type": "status",
                "status": "error",
                "message": "无法连接到语音服务"
            })
            await websocket.close()
            return

        await websocket.send_json({
            "type": "status",
            "status": "connected",
            "message": "已连接"
        })

        # 启动接收循环
        receive_task = asyncio.create_task(client.receive_loop())

        # 发送开场白
        await client.say_hello()

        # 处理前端消息
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get("type")

                if msg_type == "audio":
                    # 接收音频数据并发送给豆包
                    audio_data = base64.b64decode(message.get("data", ""))
                    if audio_data:
                        await client.send_audio(audio_data)

                elif msg_type == "stop":
                    # 用户请求停止
                    break

            except WebSocketDisconnect:
                print("WebSocket 断开连接")
                break
            except json.JSONDecodeError:
                print("无效的 JSON 消息")
                continue
            except Exception as e:
                print(f"处理消息错误: {e}")
                continue

    except Exception as e:
        print(f"WebSocket 错误: {e}")
        try:
            await websocket.send_json({
                "type": "status",
                "status": "error",
                "message": str(e)
            })
        except:
            pass

    finally:
        # 清理
        if receive_task:
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

        if client:
            try:
                await client.finish_session()
                await client.finish_connection()
                await client.close()
            except:
                pass

        try:
            await websocket.close()
        except:
            pass
