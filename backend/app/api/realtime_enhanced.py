"""
实时对话 WebSocket API - 增强模式
支持 dialog_context 预设示例 + 实时干预
"""
import asyncio
import json
import base64
from urllib.parse import parse_qs
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.doubao_realtime_enhanced import DoubaoRealtimeEnhancedClient
from app.services.intervention_service import intervention_service
from app.database import SessionLocal
from app.models import Message, User
from app.auth import decode_token
from app.services.era_memory_service import era_memory_service

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
        print(f"[Enhanced] 保存消息: {role} - {content[:50]}...")
    except Exception as e:
        print(f"[Enhanced] 保存消息失败: {e}")
        db.rollback()
    finally:
        db.close()


def authenticate_ws(query_params: dict) -> str:
    """从 WebSocket query params 中解析 token，返回 user_id"""
    token = query_params.get("token", [None])[0]
    if not token:
        raise ValueError("缺少认证令牌")
    return decode_token(token)


@router.websocket("/dialog")
async def realtime_dialog_enhanced(websocket: WebSocket):
    """
    增强模式实时对话 WebSocket 端点

    与普通模式的区别：
    1. 使用精简版 system_role
    2. 注入 dialog_context 预设示例
    3. 在 ASR 结束后进行干预判断

    前端发送消息格式:
    - {"type": "audio", "data": "<base64 encoded pcm audio>"}
    - {"type": "stop"}

    后端发送消息格式:
    - {"type": "audio", "data": "<base64 encoded pcm audio>"}
    - {"type": "text", "text_type": "asr|response", "content": "..."}
    - {"type": "event", "event": <event_code>, "payload": {...}}
    - {"type": "status", "status": "connected|disconnected|error", "message": "..."}
    - {"type": "intervention", "triggered": true/false}  # 干预状态通知
    """
    await websocket.accept()

    # 解析参数
    query_string = websocket.scope.get("query_string", b"").decode()
    query_params = parse_qs(query_string)

    # 认证
    try:
        user_id = authenticate_ws(query_params)
    except Exception as e:
        await websocket.send_json({
            "type": "status",
            "status": "error",
            "message": f"认证失败: {str(e)}"
        })
        await websocket.close(code=4001)
        return

    speaker = query_params.get("speaker", [None])[0]
    recorder_name = query_params.get("recorder_name", ["小安"])[0]
    conversation_id = query_params.get("conversation_id", [None])[0]
    custom_topic = query_params.get("topic", [None])[0]
    custom_greeting = query_params.get("greeting", [None])[0]

    print(f"[Enhanced] 收到连接请求")
    print(f"  - user_id: {user_id}")
    print(f"  - conversation_id: {conversation_id}")
    print(f"  - topic: {custom_topic}")

    client = None
    receive_task = None

    # 对话状态
    current_asr_text = ""
    current_response_text = ""
    recent_messages = []  # 最近几轮对话，用于干预判断
    era_memories = ""  # 时代记忆

    # 获取用户信息和时代记忆
    user_nickname = None
    if user_id:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user_nickname = user.preferred_name or user.nickname
                # 获取时代记忆
                if user.birth_year:
                    era_memories = era_memory_service.get_for_user(db, user.birth_year)
                if not era_memories:
                    era_memories = user.era_memories or ""
                print(f"[Enhanced] 用户: {user_nickname}, 时代记忆: {len(era_memories)} 字")
        finally:
            db.close()

    async def on_audio(audio_data: bytes):
        """收到音频回复"""
        try:
            await websocket.send_json({
                "type": "audio",
                "data": base64.b64encode(audio_data).decode()
            })
        except Exception as e:
            print(f"[Enhanced] 发送音频失败: {e}")

    async def on_text(text_type: str, content: str):
        """收到文本"""
        nonlocal current_asr_text, current_response_text

        try:
            await websocket.send_json({
                "type": "text",
                "text_type": text_type,
                "content": content
            })

            if text_type == "asr":
                current_asr_text = content
            elif text_type == "response":
                current_response_text += content

        except Exception as e:
            print(f"[Enhanced] 发送文本失败: {e}")

    async def on_event(event: int, payload: dict):
        """收到事件"""
        nonlocal current_asr_text, current_response_text, recent_messages

        try:
            await websocket.send_json({
                "type": "event",
                "event": event,
                "payload": payload if isinstance(payload, dict) else {}
            })

            if event == 350:  # TTS 开始
                current_response_text = ""

            elif event == 359:  # TTS 结束 - 保存 AI 回复
                if current_response_text and conversation_id:
                    save_message(conversation_id, "assistant", current_response_text)
                    recent_messages.append({
                        "role": "assistant",
                        "content": current_response_text
                    })
                    # 只保留最近 10 条
                    if len(recent_messages) > 10:
                        recent_messages = recent_messages[-10:]
                current_response_text = ""

        except Exception as e:
            print(f"[Enhanced] 发送事件失败: {e}")

    async def on_asr_ended(asr_text: str):
        """ASR 结束 - 保存用户消息并进行干预判断"""
        nonlocal recent_messages

        if not asr_text:
            return

        # 保存用户消息
        if conversation_id:
            save_message(conversation_id, "user", asr_text)

        recent_messages.append({
            "role": "user",
            "content": asr_text
        })
        if len(recent_messages) > 10:
            recent_messages = recent_messages[-10:]

        # 进行干预判断
        try:
            guidance = await intervention_service.judge_and_intervene(
                topic=custom_topic or "自由聊天",
                recent_messages=recent_messages,
                user_message=asr_text,
                era_memories=era_memories
            )

            if guidance:
                # 注入干预引导
                await client.inject_guidance(guidance)
                await websocket.send_json({
                    "type": "intervention",
                    "triggered": True,
                    "guidance": guidance  # 返回干预内容，供前端 debug 显示
                })
            else:
                await websocket.send_json({
                    "type": "intervention",
                    "triggered": False,
                    "guidance": None
                })

        except Exception as e:
            print(f"[Enhanced] 干预判断失败: {e}")
            import traceback
            traceback.print_exc()

    try:
        # 创建增强版客户端
        client = DoubaoRealtimeEnhancedClient(
            speaker=speaker,
            recorder_name=recorder_name,
            user_nickname=user_nickname,
            topic=custom_topic,
            on_audio=lambda data: asyncio.create_task(on_audio(data)),
            on_text=lambda t, c: asyncio.create_task(on_text(t, c)),
            on_event=lambda e, p: asyncio.create_task(on_event(e, p)),
            on_asr_ended=lambda t: asyncio.create_task(on_asr_ended(t)),
        )

        # 连接
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
            "message": "已连接（增强模式）"
        })

        # 启动接收循环
        receive_task = asyncio.create_task(client.receive_loop())

        # 发送开场白
        greeting = custom_greeting or "您好，今天想听您讲讲您的故事。您最近有没有想起什么往事？"
        await client.say_hello(greeting)

        # 处理前端消息
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get("type")

                if msg_type == "audio":
                    audio_data = base64.b64decode(message.get("data", ""))
                    if audio_data:
                        await client.send_audio(audio_data)

                elif msg_type == "stop":
                    break

            except WebSocketDisconnect:
                print("[Enhanced] WebSocket 断开连接")
                break
            except json.JSONDecodeError:
                print("[Enhanced] 无效的 JSON 消息")
                continue
            except Exception as e:
                print(f"[Enhanced] 处理消息错误: {e}")
                continue

    except Exception as e:
        print(f"[Enhanced] WebSocket 错误: {e}")
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
