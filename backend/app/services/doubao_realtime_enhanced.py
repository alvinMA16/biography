"""
豆包实时对话服务 - 增强版
支持 dialog_context 预设示例 + 实时干预注入
"""
import gzip
import json
import uuid
import asyncio
from typing import Dict, Any, Optional, Callable, List
import websockets

from app.config import settings
from app.prompts import realtime_chat_enhanced, dialog_examples


# Protocol constants (复用原有定义)
PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

# Message Types
CLIENT_FULL_REQUEST = 0b0001
CLIENT_AUDIO_ONLY_REQUEST = 0b0010
SERVER_FULL_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# Message Type Specific Flags
MSG_WITH_EVENT = 0b0100
NEG_SEQUENCE = 0b0010

# Serialization
NO_SERIALIZATION = 0b0000
JSON_SERIAL = 0b0001

# Compression
GZIP = 0b0001


def generate_header(
    message_type=CLIENT_FULL_REQUEST,
    message_type_specific_flags=MSG_WITH_EVENT,
    serial_method=JSON_SERIAL,
    compression_type=GZIP,
):
    """生成协议头"""
    header = bytearray()
    header_size = 1
    header.append((PROTOCOL_VERSION << 4) | header_size)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serial_method << 4) | compression_type)
    header.append(0x00)  # reserved
    return header


def parse_response(res) -> Dict[str, Any]:
    """解析服务器响应"""
    if isinstance(res, str) or len(res) < 4:
        return {}

    header_size = res[0] & 0x0f
    message_type = res[1] >> 4
    message_type_specific_flags = res[1] & 0x0f
    serialization_method = res[2] >> 4
    message_compression = res[2] & 0x0f

    payload = res[header_size * 4:]
    result = {}
    payload_msg = None
    start = 0

    if message_type in (SERVER_FULL_RESPONSE, SERVER_ACK):
        result['message_type'] = 'SERVER_FULL_RESPONSE' if message_type == SERVER_FULL_RESPONSE else 'SERVER_ACK'

        if message_type_specific_flags & NEG_SEQUENCE > 0:
            start += 4
        if message_type_specific_flags & MSG_WITH_EVENT > 0:
            result['event'] = int.from_bytes(payload[:4], "big", signed=False)
            start += 4

        payload = payload[start:]
        session_id_size = int.from_bytes(payload[:4], "big", signed=True)
        result['session_id'] = str(payload[4:session_id_size+4])
        payload = payload[4 + session_id_size:]
        payload_size = int.from_bytes(payload[:4], "big", signed=False)
        payload_msg = payload[4:]

    elif message_type == SERVER_ERROR_RESPONSE:
        result['code'] = int.from_bytes(payload[:4], "big", signed=False)
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8:]

    if payload_msg is None:
        return result

    if message_compression == GZIP and len(payload_msg) > 0:
        try:
            payload_msg = gzip.decompress(payload_msg)
        except:
            pass

    if serialization_method == JSON_SERIAL:
        try:
            payload_msg = json.loads(str(payload_msg, "utf-8"))
        except:
            pass
    elif serialization_method != NO_SERIALIZATION:
        try:
            payload_msg = str(payload_msg, "utf-8")
        except:
            pass

    result['payload_msg'] = payload_msg
    return result


class DoubaoRealtimeEnhancedClient:
    """豆包实时对话客户端 - 增强版"""

    def __init__(
        self,
        speaker: Optional[str] = None,
        recorder_name: str = "小安",
        user_nickname: Optional[str] = None,
        topic: Optional[str] = None,
        on_audio: Optional[Callable[[bytes], None]] = None,
        on_text: Optional[Callable[[str, str], None]] = None,
        on_event: Optional[Callable[[int, Dict], None]] = None,
        on_asr_ended: Optional[Callable[[str], None]] = None,  # 新增：ASR 结束回调
    ):
        self.ws = None
        self.session_id = str(uuid.uuid4())
        self.speaker = speaker or settings.doubao_speaker
        self.recorder_name = recorder_name
        self.user_nickname = user_nickname
        self.topic = topic
        self.on_audio = on_audio
        self.on_text = on_text
        self.on_event = on_event
        self.on_asr_ended = on_asr_ended
        self.is_connected = False
        self._greeting_sent = None
        self._current_asr_text = ""  # 累积 ASR 文本

    async def connect(self) -> bool:
        """建立 WebSocket 连接"""
        try:
            headers = {
                "X-Api-App-ID": settings.doubao_app_id,
                "X-Api-Access-Key": settings.doubao_access_key,
                "X-Api-Resource-Id": "volc.speech.dialog",
                "X-Api-App-Key": "PlgvMymc7f3tQnJ6",
                "X-Api-Connect-Id": str(uuid.uuid4()),
            }

            print(f"[Doubao Enhanced] 连接配置:")
            print(f"  - Speaker: {self.speaker}")
            print(f"  - Topic: {self.topic}")

            self.ws = await websockets.connect(
                settings.doubao_ws_url,
                extra_headers=headers,
                ping_interval=None
            )

            # StartConnection request
            start_conn_req = bytearray(generate_header())
            start_conn_req.extend(int(1).to_bytes(4, 'big'))
            payload = gzip.compress(b'{}')
            start_conn_req.extend(len(payload).to_bytes(4, 'big'))
            start_conn_req.extend(payload)
            await self.ws.send(start_conn_req)
            response = await self.ws.recv()
            print(f"[Doubao Enhanced] StartConnection response: {parse_response(response)}")

            # 构建精简版 system_role
            system_role = realtime_chat_enhanced.build(
                user_nickname=self.user_nickname,
                topic=self.topic
            )
            speaking_style = realtime_chat_enhanced.SPEAKING_STYLE

            # 获取预设对话示例
            dialog_context = dialog_examples.get_examples()

            # StartSession request - 带 dialog_context
            session_config = {
                "asr": {
                    "extra": {
                        "end_smooth_window_ms": settings.doubao_asr_silence_ms,
                    },
                },
                "tts": {
                    "speaker": self.speaker,
                    "audio_config": {
                        "channel": 1,
                        "format": "pcm_s16le",
                        "sample_rate": 24000
                    },
                },
                "dialog": {
                    "bot_name": self.recorder_name,
                    "system_role": system_role,
                    "speaking_style": speaking_style,
                    "dialog_context": dialog_context,  # 预设示例对话
                    "location": {
                        "city": "北京",
                    },
                    "extra": {
                        "strict_audit": False,
                        "recv_timeout": 30,
                        "input_mod": "audio"
                    }
                }
            }

            print(f"[Doubao Enhanced] dialog_context 注入 {len(dialog_context)} 条示例")

            payload = gzip.compress(json.dumps(session_config).encode())
            start_session_req = bytearray(generate_header())
            start_session_req.extend(int(100).to_bytes(4, 'big'))
            start_session_req.extend(len(self.session_id).to_bytes(4, 'big'))
            start_session_req.extend(self.session_id.encode())
            start_session_req.extend(len(payload).to_bytes(4, 'big'))
            start_session_req.extend(payload)
            await self.ws.send(start_session_req)
            response = await self.ws.recv()
            print(f"[Doubao Enhanced] StartSession response: {parse_response(response)}")

            self.is_connected = True
            return True

        except Exception as e:
            print(f"[Doubao Enhanced] 连接失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def send_audio(self, audio_data: bytes) -> None:
        """发送音频数据"""
        if not self.ws or not self.is_connected:
            return

        try:
            request = bytearray(generate_header(
                message_type=CLIENT_AUDIO_ONLY_REQUEST,
                serial_method=NO_SERIALIZATION
            ))
            request.extend(int(200).to_bytes(4, 'big'))
            request.extend(len(self.session_id).to_bytes(4, 'big'))
            request.extend(self.session_id.encode())
            payload = gzip.compress(audio_data)
            request.extend(len(payload).to_bytes(4, 'big'))
            request.extend(payload)
            await self.ws.send(request)
        except Exception as e:
            print(f"[Doubao Enhanced] 发送音频失败: {e}")

    async def say_hello(self, content: str = None) -> None:
        """发送开场白"""
        if content is None:
            content = "您好，今天想听您讲讲您的故事。"

        self._greeting_sent = content
        if not self.ws:
            return

        payload = {"content": content}
        request = bytearray(generate_header())
        request.extend(int(300).to_bytes(4, 'big'))
        payload_bytes = gzip.compress(json.dumps(payload).encode())
        request.extend(len(self.session_id).to_bytes(4, 'big'))
        request.extend(self.session_id.encode())
        request.extend(len(payload_bytes).to_bytes(4, 'big'))
        request.extend(payload_bytes)
        await self.ws.send(request)
        print(f"[Doubao Enhanced] 发送开场白: {content[:50]}...")

    async def inject_guidance(self, guidance: str) -> None:
        """
        注入干预引导
        通过 ConversationCreate 事件注入，让模型在上下文中看到这个引导
        """
        if not self.ws or not self.is_connected:
            return

        # 构造一轮"系统提示"对话
        payload = {
            "items": [
                {"role": "user", "text": f"【系统提示】{guidance}"},
                {"role": "assistant", "text": "好的，我会按这个方向引导对话。"}
            ]
        }

        print(f"[Doubao Enhanced] 注入干预引导: {guidance[:80]}...")

        request = bytearray(generate_header())
        request.extend(int(510).to_bytes(4, 'big'))  # 事件 510: ConversationCreate
        payload_bytes = gzip.compress(json.dumps(payload).encode())
        request.extend(len(self.session_id).to_bytes(4, 'big'))
        request.extend(self.session_id.encode())
        request.extend(len(payload_bytes).to_bytes(4, 'big'))
        request.extend(payload_bytes)
        await self.ws.send(request)

    async def receive_loop(self) -> None:
        """接收服务器响应的循环"""
        try:
            while self.is_connected and self.ws:
                response = await self.ws.recv()
                data = parse_response(response)

                if not data:
                    continue

                # 处理音频数据
                if data.get('message_type') == 'SERVER_ACK' and isinstance(data.get('payload_msg'), bytes):
                    if self.on_audio:
                        self.on_audio(data['payload_msg'])

                # 处理事件
                elif data.get('message_type') == 'SERVER_FULL_RESPONSE':
                    event = data.get('event')
                    payload = data.get('payload_msg', {})

                    if self.on_event:
                        self.on_event(event, payload)

                    # 处理 ASR 相关事件
                    if isinstance(payload, dict):
                        text = None
                        is_asr = False

                        # 从 results 数组中提取文本
                        results = payload.get('results', [])
                        if results and isinstance(results, list) and len(results) > 0:
                            result = results[0]
                            if isinstance(result, dict):
                                text = result.get('text')
                                is_interim = result.get('is_interim', True)

                                if event == 451:  # ASR 事件
                                    if text and not is_interim:
                                        is_asr = True
                                        self._current_asr_text = text
                                    else:
                                        text = None

                        # 兼容其他格式
                        if not text and not results:
                            text = payload.get('text') or payload.get('content')
                            if event == 451:
                                is_asr = True
                                self._current_asr_text = text or ""

                        # 发送文本回调
                        if text and self.on_text:
                            if is_asr:
                                self.on_text('asr', text)
                            elif event != 451:
                                if self._greeting_sent and text == self._greeting_sent:
                                    self._greeting_sent = None
                                else:
                                    self.on_text('response', text)

                    # ASR 结束事件 - 触发干预判断
                    if event == 459:
                        if self.on_asr_ended and self._current_asr_text:
                            self.on_asr_ended(self._current_asr_text)
                        self._current_asr_text = ""

                    # 会话结束事件
                    if event in (152, 153):
                        print(f"[Doubao Enhanced] 会话结束: event={event}")
                        break

        except asyncio.CancelledError:
            print("[Doubao Enhanced] 接收循环已取消")
        except Exception as e:
            print(f"[Doubao Enhanced] 接收消息错误: {e}")
        finally:
            self.is_connected = False

    async def finish_session(self) -> None:
        """结束会话"""
        if not self.ws:
            return

        request = bytearray(generate_header())
        request.extend(int(102).to_bytes(4, 'big'))
        payload = gzip.compress(b'{}')
        request.extend(len(self.session_id).to_bytes(4, 'big'))
        request.extend(self.session_id.encode())
        request.extend(len(payload).to_bytes(4, 'big'))
        request.extend(payload)
        await self.ws.send(request)

    async def finish_connection(self) -> None:
        """结束连接"""
        if not self.ws:
            return

        request = bytearray(generate_header())
        request.extend(int(2).to_bytes(4, 'big'))
        payload = gzip.compress(b'{}')
        request.extend(len(payload).to_bytes(4, 'big'))
        request.extend(payload)
        await self.ws.send(request)

    async def close(self) -> None:
        """关闭连接"""
        self.is_connected = False
        if self.ws:
            await self.ws.close()
            self.ws = None
