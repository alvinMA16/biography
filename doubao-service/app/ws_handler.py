"""
WebSocket 处理器
处理来自主 Backend 的 WebSocket 连接，管理与豆包 API 的通信
"""
import asyncio
import json
import base64
from fastapi import WebSocket, WebSocketDisconnect

from app.doubao_client import DoubaoClient


async def handle_doubao_session(websocket: WebSocket):
    """
    处理一个完整的豆包会话

    协议:
    - Backend -> Doubao Service:
      {"type": "init", "config": {...}}  # 初始化配置
      {"type": "audio", "data": "<base64>"}  # 音频数据
      {"type": "say_hello", "content": "..."}  # 发送开场白
      {"type": "inject_guidance", "guidance": "...", "mechanism": "...", "intervention_type": "..."}  # 干预注入
      {"type": "stop"}  # 停止会话

    - Doubao Service -> Backend:
      {"type": "status", "status": "connected|error", "message": "..."}
      {"type": "audio", "data": "<base64>"}  # 音频数据
      {"type": "text", "text_type": "asr|response", "content": "..."}
      {"type": "event", "event": <code>, "payload": {...}}
    """
    await websocket.accept()

    client = None
    receive_task = None

    async def on_audio(audio_data: bytes):
        """收到豆包音频，转发给 Backend"""
        try:
            await websocket.send_json({
                "type": "audio",
                "data": base64.b64encode(audio_data).decode()
            })
        except Exception as e:
            print(f"[WS Handler] 发送音频失败: {e}")

    async def on_text(text_type: str, content: str):
        """收到豆包文本，转发给 Backend"""
        try:
            await websocket.send_json({
                "type": "text",
                "text_type": text_type,
                "content": content
            })
        except Exception as e:
            print(f"[WS Handler] 发送文本失败: {e}")

    async def on_event(event: int, payload: dict):
        """收到豆包事件，转发给 Backend"""
        try:
            await websocket.send_json({
                "type": "event",
                "event": event,
                "payload": payload if isinstance(payload, dict) else {}
            })
        except Exception as e:
            print(f"[WS Handler] 发送事件失败: {e}")

    try:
        # 等待 init 消息
        init_msg = await asyncio.wait_for(websocket.receive_json(), timeout=30)
        if init_msg.get("type") != "init":
            await websocket.send_json({
                "type": "status",
                "status": "error",
                "message": "第一条消息必须是 init 类型"
            })
            await websocket.close()
            return

        config = init_msg.get("config", {})
        print(f"[WS Handler] 收到 init 配置: mode={config.get('mode')}, topic={config.get('topic')}")

        # 创建豆包客户端
        client = DoubaoClient(
            speaker=config.get("speaker"),
            recorder_name=config.get("recorder_name", "小安"),
            mode=config.get("mode", "normal"),
            user_nickname=config.get("user_nickname"),
            user_formal_name=config.get("user_formal_name"),
            user_gender=config.get("user_gender"),
            topic=config.get("topic"),
            chat_context=config.get("chat_context"),
            era_memories=config.get("era_memories"),
            dialog_context=config.get("dialog_context"),
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
                "message": "无法连接到豆包语音服务"
            })
            await websocket.close()
            return

        await websocket.send_json({
            "type": "status",
            "status": "connected",
            "message": "已连接到豆包"
        })

        # 启动接收循环
        receive_task = asyncio.create_task(client.receive_loop())

        # 处理来自 Backend 的消息
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get("type")

                if msg_type == "audio":
                    # 音频数据，转发给豆包
                    audio_data = base64.b64decode(message.get("data", ""))
                    if audio_data:
                        await client.send_audio(audio_data)

                elif msg_type == "say_hello":
                    # 发送开场白
                    content = message.get("content")
                    await client.say_hello(content)

                elif msg_type == "inject_guidance":
                    # 干预注入
                    guidance = message.get("guidance", "")
                    mechanism = message.get("mechanism", "instruction")
                    intervention_type = message.get("intervention_type", "")
                    await client.inject_guidance(guidance, mechanism, intervention_type)

                elif msg_type == "conversation_create":
                    # 注入对话历史
                    user_text = message.get("user_text", "")
                    assistant_text = message.get("assistant_text", "")
                    await client.conversation_create(user_text, assistant_text)

                elif msg_type == "stop":
                    # 停止会话
                    break

            except WebSocketDisconnect:
                print("[WS Handler] Backend WebSocket 断开连接")
                break
            except json.JSONDecodeError:
                print("[WS Handler] 无效的 JSON 消息")
                continue
            except Exception as e:
                print(f"[WS Handler] 处理消息错误: {e}")
                continue

    except asyncio.TimeoutError:
        print("[WS Handler] 等待 init 消息超时")
        try:
            await websocket.send_json({
                "type": "status",
                "status": "error",
                "message": "等待初始化超时"
            })
        except:
            pass

    except Exception as e:
        print(f"[WS Handler] 会话错误: {e}")
        import traceback
        traceback.print_exc()
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
