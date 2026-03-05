"""
豆包实时对话客户端
合并普通模式和增强模式，支持所有对话场景
"""
import gzip
import json
import uuid
import asyncio
from typing import Dict, Any, Optional, Callable, List
import websockets

from app.config import settings


# Protocol constants
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


# 不同干预类型的注入话术
INJECTION_FRAMES = {
    "important_clue": (
        "【系统指令 - 必须执行】用户刚才提到了一个重要线索，你需要追问把信息收集完整。"
        "先简短回应用户，然后从以下方向中选一个去追问具体细节：\n{guidance}",
        "明白了，我会抓住这个线索，把具体信息问清楚。"
    ),
    "stagnation": (
        "【系统指令 - 必须执行】对话在同一个点上打转了，用户说不出新内容了。"
        "你需要换一个全新的方向，去了解用户人生中其他方面的信息。"
        "先简短回应，然后从以下方向中选一个最自然的展开：\n{guidance}",
        "明白了，我会换个方向，聊点不一样的。"
    ),
    "topic_drift": (
        "【系统指令 - 必须执行】你刚才的提问跑偏了，陷入了操作细节或者在反复追问感受。"
        "请调整方向，去收集有用的人生信息——具体的人、事、经历。"
        "先简短回应用户，然后从以下方向中选一个展开：\n{guidance}",
        "明白了，我会调整方向，去问具体的人和事。"
    ),
}


class DoubaoClient:
    """豆包实时对话客户端 - 统一版本"""

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
        self.session_id = str(uuid.uuid4())
        self.speaker = speaker or settings.doubao_speaker
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
        self._skip_greeting_echo = False
        self._greeting_sent = None

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

            print(f"[Doubao] 连接配置:")
            print(f"  - URL: {settings.doubao_ws_url}")
            print(f"  - Mode: {self.mode}")
            print(f"  - Speaker: {self.speaker}")

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
            print(f"[Doubao] StartConnection response: {parse_response(response)}")

            # 根据模式构建 system_role 和配置
            system_role, speaking_style, dialog_context = self._build_session_config()

            # StartSession request
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

            # 增强模式添加 dialog_context
            if dialog_context:
                session_config["dialog"]["dialog_context"] = dialog_context
                print(f"[Doubao] dialog_context 注入 {len(dialog_context)} 条")

            payload = gzip.compress(json.dumps(session_config).encode())
            start_session_req = bytearray(generate_header())
            start_session_req.extend(int(100).to_bytes(4, 'big'))
            start_session_req.extend(len(self.session_id).to_bytes(4, 'big'))
            start_session_req.extend(self.session_id.encode())
            start_session_req.extend(len(payload).to_bytes(4, 'big'))
            start_session_req.extend(payload)
            await self.ws.send(start_session_req)
            response = await self.ws.recv()
            print(f"[Doubao] StartSession response: {parse_response(response)}")

            self.is_connected = True
            return True

        except Exception as e:
            print(f"[Doubao] 连接失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _build_session_config(self):
        """根据模式构建会话配置"""
        from app.prompts import realtime_profile_collection, realtime_chat, realtime_chat_enhanced, dialog_examples

        dialog_context = []

        if self.mode == "profile_collection":
            system_role = realtime_profile_collection.build(
                recorder_name=self.recorder_name,
                user_name=self.user_formal_name,
                gender=self.user_gender,
            )
            speaking_style = realtime_profile_collection.SPEAKING_STYLE

        elif self.mode == "enhanced":
            system_role = realtime_chat_enhanced.build(
                user_nickname=self.user_nickname,
                topic=self.topic
            )
            speaking_style = realtime_chat_enhanced.SPEAKING_STYLE

            # 获取预设对话示例
            dialog_context = dialog_examples.get_examples()

            # 预加载时代记忆
            if self.era_memories:
                condensed = self.era_memories[:500]
                if len(self.era_memories) > 500:
                    condensed += "……"
                dialog_context.extend([
                    {"role": "user", "text": f"【背景知识】以下是与用户年代相关的历史背景，在对话中可以自然地运用：{condensed}"},
                    {"role": "assistant", "text": "好的，我了解了这些历史背景，会在合适的时候自然地融入对话。"},
                ])
                print(f"[Doubao] 预加载时代记忆: {len(condensed)} 字")

        else:  # normal mode
            system_role = realtime_chat.build(
                self.user_nickname,
                self.topic,
                self.chat_context
            )
            speaking_style = realtime_chat.SPEAKING_STYLE

        # 如果外部传入了 dialog_context，追加
        if self.dialog_context:
            dialog_context.extend(self.dialog_context)

        return system_role, speaking_style, dialog_context

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
            print(f"[Doubao] 发送音频失败: {e}")

    async def say_hello(self, content: str = None) -> None:
        """发送开场白"""
        import random

        GREETINGS = [
            "您好！今天想听您讲讲您的故事。您最近有没有想起什么往事？",
            "您好！很高兴能陪您聊聊天。您小时候住在哪里？那时候的生活是什么样的？",
            "您好！今天想请您讲讲您的人生故事。您还记得小时候印象最深的一件事吗？",
        ]

        if content is None:
            content = random.choice(GREETINGS)

        # 标记跳过开场白回显
        if self.mode != "enhanced":
            self._skip_greeting_echo = True
        else:
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
        print(f"[Doubao] 发送开场白: {content[:50]}...")

    async def conversation_create(self, user_text: str, assistant_text: str) -> None:
        """向对话中注入一条历史记录"""
        if not self.ws or not self.is_connected:
            return

        payload = {
            "items": [
                {"role": "user", "text": user_text},
                {"role": "assistant", "text": assistant_text}
            ]
        }

        print(f"[Doubao] ConversationCreate: 注入背景信息 ({len(user_text)} 字符)")

        request = bytearray(generate_header())
        request.extend(int(510).to_bytes(4, 'big'))
        payload_bytes = gzip.compress(json.dumps(payload).encode())
        request.extend(len(self.session_id).to_bytes(4, 'big'))
        request.extend(self.session_id.encode())
        request.extend(len(payload_bytes).to_bytes(4, 'big'))
        request.extend(payload_bytes)
        await self.ws.send(request)

    async def inject_guidance(self, guidance: str, mechanism: str = "instruction", intervention_type: str = "") -> None:
        """
        注入干预引导

        Args:
            guidance: 干预内容
            mechanism: 注入机制 - "instruction" 或 "knowledge"
            intervention_type: 干预类型 - topic_drift/stagnation/important_clue/era_trigger
        """
        if not self.ws or not self.is_connected:
            return

        if mechanism == "knowledge":
            payload = {
                "items": [
                    {"role": "user", "text": f"【背景知识】{guidance} 你可以用这些背景自然地和用户聊这段经历。"},
                    {"role": "assistant", "text": "好的，我了解了这段历史背景。"}
                ]
            }
        else:
            frame = INJECTION_FRAMES.get(intervention_type)
            if frame:
                user_text = frame[0].format(guidance=guidance)
                assistant_text = frame[1]
            else:
                user_text = f"【系统指令 - 必须执行】请根据用户的回答，从以下方向中选一个最自然的展开：\n{guidance}"
                assistant_text = "收到，我会选择最合适的方向。"

            payload = {
                "items": [
                    {"role": "user", "text": user_text},
                    {"role": "assistant", "text": assistant_text}
                ]
            }

        print(f"[Doubao] 注入干预[{mechanism}]: {guidance[:80]}...")

        request = bytearray(generate_header())
        request.extend(int(510).to_bytes(4, 'big'))
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

                    # 开场白回显结束
                    if event == 359 and self._skip_greeting_echo:
                        print(f"[Doubao] 开场白回显 TTS 结束，恢复文本转发")
                        self._skip_greeting_echo = False

                    if self.on_event:
                        self.on_event(event, payload)

                    # 提取文本内容
                    if isinstance(payload, dict):
                        text = None
                        is_asr = False

                        results = payload.get('results', [])
                        if results and isinstance(results, list) and len(results) > 0:
                            result = results[0]
                            if isinstance(result, dict):
                                text = result.get('text')
                                is_interim = result.get('is_interim', True)

                                if event == 451:  # ASR 事件
                                    if text and not is_interim:
                                        is_asr = True
                                    else:
                                        text = None

                        if not text and not results:
                            text = payload.get('text') or payload.get('content')
                            if event == 451:
                                is_asr = True

                        # 发送文本
                        if text and self.on_text:
                            if is_asr:
                                print(f"[Doubao] ASR 最终结果: {text[:50]}...")
                                self.on_text('asr', text)
                            elif event != 451:
                                # AI 回复
                                if self._skip_greeting_echo:
                                    pass
                                elif self._greeting_sent and text == self._greeting_sent:
                                    self._greeting_sent = None
                                else:
                                    self.on_text('response', text)

                    # 会话结束事件
                    if event in (152, 153):
                        print(f"[Doubao] 会话结束: event={event}")
                        break

        except asyncio.CancelledError:
            print("[Doubao] 接收循环已取消")
        except Exception as e:
            print(f"[Doubao] 接收消息错误: {e}")
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
