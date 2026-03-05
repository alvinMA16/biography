"""
豆包服务代理
通过 WebSocket 连接到独立的 Doubao Service 微服务
"""
import asyncio
import json
import base64
from typing import Optional, Callable, Dict, Any, List

import websockets

from app.config import settings


class DoubaoProxy:
    """豆包服务代理类"""

    def __init__(
        self,
        speaker: Optional[str] = None,
        recorder_name: str = "小安",
        mode: str = "normal",  # normal, enhanced, profile_collection
        user_nickname: Optional[str] = None,
        user_formal_name: Optional[str] = None,
        user_gender: Optional[str] = None,
        topic: Optional[str] = None,
        chat_context: Optional[str] = None,
        era_memories: Optional[str] = None,
        dialog_context: Optional[List[Dict]] = None,
        on_audio: Optional[Callable[[bytes], None]] = None,
        on_text: Optional[Callable[[str, str], None]] = None,
        on_event: Optional[Callable[[int, Dict], None]] = None,
    ):
        self.ws = None
        self.speaker = speaker
        self.recorder_name = recorder_name
        self.mode = mode
        self.user_nickname = user_nickname
        self.user_formal_name = user_formal_name
        self.user_gender = user_gender
        self.topic = topic
        self.chat_context = chat_context
        self.era_memories = era_memories
        self.dialog_context = dialog_context or []
        self.on_audio = on_audio
        self.on_text = on_text
        self.on_event = on_event
        self.is_connected = False

    async def connect(self) -> bool:
        """连接到 Doubao Service"""
        try:
            print(f"[Proxy] 连接到 Doubao Service: {settings.doubao_service_url}")

            self.ws = await websockets.connect(
                settings.doubao_service_url,
                ping_interval=None,  # FastAPI WebSocket 不需要客户端 ping
            )

            # 发送 init 消息
            init_msg = {
                "type": "init",
                "config": {
                    "speaker": self.speaker,
                    "recorder_name": self.recorder_name,
                    "mode": self.mode,
                    "user_nickname": self.user_nickname,
                    "user_formal_name": self.user_formal_name,
                    "user_gender": self.user_gender,
                    "topic": self.topic,
                    "chat_context": self.chat_context,
                    "era_memories": self.era_memories,
                    "dialog_context": self.dialog_context,
                }
            }
            await self.ws.send(json.dumps(init_msg))
            print(f"[Proxy] 发送 init: mode={self.mode}, topic={self.topic}")

            # 等待连接确认
            response = await asyncio.wait_for(self.ws.recv(), timeout=30)
            data = json.loads(response)

            if data.get("type") == "status":
                if data.get("status") == "connected":
                    self.is_connected = True
                    print(f"[Proxy] 连接成功: {data.get('message')}")
                    return True
                else:
                    print(f"[Proxy] 连接失败: {data.get('message')}")
                    return False

            print(f"[Proxy] 意外响应: {data}")
            return False

        except Exception as e:
            print(f"[Proxy] 连接错误: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def send_audio(self, audio_data: bytes) -> None:
        """发送音频数据"""
        if not self.ws or not self.is_connected:
            return

        try:
            msg = {
                "type": "audio",
                "data": base64.b64encode(audio_data).decode()
            }
            await self.ws.send(json.dumps(msg))
        except Exception as e:
            print(f"[Proxy] 发送音频失败: {e}")

    async def say_hello(self, content: str = None) -> None:
        """发送开场白"""
        if not self.ws or not self.is_connected:
            return

        try:
            msg = {
                "type": "say_hello",
                "content": content
            }
            await self.ws.send(json.dumps(msg))
            print(f"[Proxy] 发送开场白: {(content or '')[:50]}...")
        except Exception as e:
            print(f"[Proxy] 发送开场白失败: {e}")

    async def inject_guidance(self, guidance: str, mechanism: str = "instruction", intervention_type: str = "") -> None:
        """注入干预引导"""
        if not self.ws or not self.is_connected:
            return

        try:
            msg = {
                "type": "inject_guidance",
                "guidance": guidance,
                "mechanism": mechanism,
                "intervention_type": intervention_type
            }
            await self.ws.send(json.dumps(msg))
            print(f"[Proxy] 注入干预: {guidance[:50]}...")
        except Exception as e:
            print(f"[Proxy] 注入干预失败: {e}")

    async def conversation_create(self, user_text: str, assistant_text: str) -> None:
        """向对话中注入历史记录"""
        if not self.ws or not self.is_connected:
            return

        try:
            msg = {
                "type": "conversation_create",
                "user_text": user_text,
                "assistant_text": assistant_text
            }
            await self.ws.send(json.dumps(msg))
            print(f"[Proxy] 注入对话历史")
        except Exception as e:
            print(f"[Proxy] 注入对话历史失败: {e}")

    async def receive_loop(self) -> None:
        """接收 Doubao Service 消息并转发"""
        try:
            while self.is_connected and self.ws:
                response = await self.ws.recv()
                data = json.loads(response)

                msg_type = data.get("type")

                if msg_type == "audio":
                    # 音频数据
                    if self.on_audio:
                        audio_bytes = base64.b64decode(data.get("data", ""))
                        self.on_audio(audio_bytes)

                elif msg_type == "text":
                    # 文本消息
                    if self.on_text:
                        self.on_text(data.get("text_type"), data.get("content"))

                elif msg_type == "event":
                    # 事件
                    if self.on_event:
                        self.on_event(data.get("event"), data.get("payload", {}))

                elif msg_type == "status":
                    # 状态消息
                    if data.get("status") == "error":
                        print(f"[Proxy] Doubao Service 错误: {data.get('message')}")
                        break

        except asyncio.CancelledError:
            print("[Proxy] 接收循环已取消")
        except websockets.exceptions.ConnectionClosed:
            print("[Proxy] WebSocket 连接已关闭")
        except Exception as e:
            print(f"[Proxy] 接收消息错误: {e}")
        finally:
            self.is_connected = False

    async def finish_session(self) -> None:
        """结束会话（发送 stop 消息）"""
        if not self.ws:
            return

        try:
            msg = {"type": "stop"}
            await self.ws.send(json.dumps(msg))
        except:
            pass

    async def finish_connection(self) -> None:
        """结束连接（空操作，由 close 处理）"""
        pass

    async def close(self) -> None:
        """关闭连接"""
        self.is_connected = False
        if self.ws:
            try:
                await self.ws.close()
            except:
                pass
            self.ws = None
