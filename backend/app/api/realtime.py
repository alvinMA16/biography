"""
实时对话 WebSocket API
前端通过 WebSocket 连接，发送音频，接收音频和文本回复
"""
import asyncio
import json
import base64
from urllib.parse import parse_qs
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.doubao_realtime import DoubaoRealtimeClient
from app.services.greeting_service import greeting_service
from app.database import SessionLocal
from app.models import Message, User

router = APIRouter()


def save_message(conversation_id: str, role: str, content: str):
    """保存消息到数据库"""
    if not conversation_id or not content or not content.strip():
        return

    db = SessionLocal()
    try:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content.strip()
        )
        db.add(message)
        db.commit()
        print(f"[Realtime] 保存消息: {role} - {content[:50]}...")
    except Exception as e:
        print(f"[Realtime] 保存消息失败: {e}")
        db.rollback()
    finally:
        db.close()


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

    # 从 URL 查询参数中获取参数
    query_string = websocket.scope.get("query_string", b"").decode()
    query_params = parse_qs(query_string)
    speaker = query_params.get("speaker", [None])[0]
    recorder_name = query_params.get("recorder_name", ["小安"])[0]  # 记录师名字
    conversation_id = query_params.get("conversation_id", [None])[0]
    user_id = query_params.get("user_id", [None])[0]
    mode = query_params.get("mode", ["normal"])[0]  # normal 或 profile_collection
    print(f"[Realtime] 收到连接请求, speaker={speaker}, recorder_name={recorder_name}, conversation_id={conversation_id}, user_id={user_id}, mode={mode}")

    client = None
    receive_task = None

    # 用于累积文本内容
    current_asr_text = ""
    current_response_text = ""

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
        nonlocal current_asr_text, current_response_text

        try:
            await websocket.send_json({
                "type": "text",
                "text_type": text_type,
                "content": content
            })

            # 累积文本
            if text_type == "asr":
                current_asr_text = content  # ASR 是渐进式识别，每次是完整结果
                print(f"[Realtime] ASR 文本: {content}")
            elif text_type == "response":
                current_response_text += content  # AI 回复是增量发送，需要累积

        except Exception as e:
            print(f"发送文本失败: {e}")

    async def on_event(event: int, payload: dict):
        """收到事件"""
        nonlocal current_asr_text, current_response_text

        try:
            await websocket.send_json({
                "type": "event",
                "event": event,
                "payload": payload if isinstance(payload, dict) else {}
            })

            # 根据事件保存消息
            if event == 350:
                # TTS 开始 - 重置 AI 回复文本，准备累积新内容
                current_response_text = ""

            elif event == 459:
                # 用户说完 - 保存用户消息
                if current_asr_text and conversation_id:
                    save_message(conversation_id, "user", current_asr_text)
                    current_asr_text = ""

            elif event == 359:
                # TTS 结束 - 保存 AI 回复
                if current_response_text and conversation_id:
                    save_message(conversation_id, "assistant", current_response_text)
                    current_response_text = ""

        except Exception as e:
            print(f"发送事件失败: {e}")

    try:
        # 检查用户是否需要收集信息
        actual_mode = mode
        if user_id and mode != "profile_collection":
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user and not user.profile_completed:
                    actual_mode = "profile_collection"
                    print(f"[Realtime] 用户未完成信息收集，切换到 profile_collection 模式")
            finally:
                db.close()

        # 创建豆包客户端
        client = DoubaoRealtimeClient(
            speaker=speaker,  # 传入音色参数
            recorder_name=recorder_name,  # 传入记录师名字
            mode=actual_mode,  # 传入模式
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

        # 根据模式选择开场白
        greeting = None

        if actual_mode == "profile_collection":
            # 信息收集模式
            greeting = f"您好！我是{recorder_name}，很高兴认识您。在开始记录您的故事之前，我想先了解一下您。请问我应该怎么称呼您呢？"
        elif user_id:
            # 正常模式，从候选池获取开场白
            db = SessionLocal()
            try:
                greeting = greeting_service.get_random_greeting(db, user_id)
            finally:
                db.close()

        # 发送开场白
        await client.say_hello(greeting)

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


@router.websocket("/preview")
async def realtime_preview(websocket: WebSocket):
    """
    TTS 预览端点 - 用指定音色朗读一段文字
    参数:
    - speaker: 音色
    - text: 要朗读的文字
    """
    await websocket.accept()

    # 解析参数
    query_string = websocket.scope.get("query_string", b"").decode()
    query_params = parse_qs(query_string)
    speaker = query_params.get("speaker", [None])[0]
    text = query_params.get("text", ["您好"])[0]

    print(f"[Preview] speaker={speaker}, text={text}")

    client = None
    receive_task = None
    tts_done = asyncio.Event()

    async def on_audio(audio_data: bytes):
        try:
            await websocket.send_json({
                "type": "audio",
                "data": base64.b64encode(audio_data).decode()
            })
        except Exception as e:
            print(f"发送预览音频失败: {e}")

    async def on_event(event: int, payload: dict):
        # TTS 结束事件
        if event == 359:
            tts_done.set()

    try:
        client = DoubaoRealtimeClient(
            speaker=speaker,
            on_audio=lambda data: asyncio.create_task(on_audio(data)),
            on_event=lambda e, p: asyncio.create_task(on_event(e, p)),
        )

        connected = await client.connect()
        if not connected:
            await websocket.send_json({"type": "error", "message": "连接失败"})
            await websocket.close()
            return

        # 启动接收循环
        receive_task = asyncio.create_task(client.receive_loop())

        # 发送要朗读的文字
        await client.say_hello(text)

        # 等待 TTS 完成（最多10秒）
        try:
            await asyncio.wait_for(tts_done.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass

        await websocket.send_json({"type": "done"})

    except Exception as e:
        print(f"Preview 错误: {e}")

    finally:
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
