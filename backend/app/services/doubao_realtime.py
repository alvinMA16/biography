"""
豆包实时对话服务
基于 WebSocket 的端到端语音对话（ASR + LLM + TTS）
"""
import gzip
import json
import uuid
import asyncio
from typing import Dict, Any, Optional, Callable
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


class DoubaoRealtimeClient:
    """豆包实时对话客户端"""

    def __init__(
        self,
        speaker: Optional[str] = None,
        on_audio: Optional[Callable[[bytes], None]] = None,
        on_text: Optional[Callable[[str, str], None]] = None,  # (type, text)
        on_event: Optional[Callable[[int, Dict], None]] = None,
    ):
        self.ws = None
        self.session_id = str(uuid.uuid4())
        self.speaker = speaker or settings.doubao_speaker  # 使用传入的音色或默认音色
        self.on_audio = on_audio
        self.on_text = on_text
        self.on_event = on_event
        self.is_connected = False

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
            print(f"  - App ID: {settings.doubao_app_id[:8]}..." if settings.doubao_app_id else "  - App ID: (未配置)")
            print(f"  - Access Key: {settings.doubao_access_key[:8]}..." if settings.doubao_access_key else "  - Access Key: (未配置)")
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
            print(f"StartConnection response: {parse_response(response)}")

            # StartSession request
            session_config = {
                "asr": {
                    "extra": {
                        "end_smooth_window_ms": 1500,
                    },
                },
                "tts": {
                    "speaker": self.speaker,
                    "audio_config": {
                        "channel": 1,
                        "format": "pcm_s16le",  # 16bit位深，小端序
                        "sample_rate": 24000
                    },
                },
                "dialog": {
                    "bot_name": "小辈",
                    "system_role": """你是一位正在采访长辈、帮助他们留下人生故事的晚辈。你的目标是引导长辈讲出有深度、有画面感、有情感的回忆。

## 核心原则
你不是在闲聊，而是在做一次有价值的人生访谈。每个问题都要能挖掘出可以写进回忆录的素材。

## 提问技巧

### 1. 追问具体场景，而非泛泛而谈
- 差：那时候生活怎么样？
- 好：您还记得那时候家里吃的最好的一顿饭是什么吗？
- 好：那个冬天您是怎么取暖的？

### 2. 追问转折点和重要决定
- 您当时为什么选择了这条路？有没有犹豫过？
- 如果当时选了另一条路，您觉得人生会有什么不同？
- 那件事之后，您的想法有什么变化吗？

### 3. 追问人物关系和互动
- 您和他/她第一次见面是什么情景？
- 你们之间有没有发生过什么让您印象特别深的事？
- 他/她说过什么话让您一直记到现在？

### 4. 追问感官细节
- 那个地方是什么样子的？您还记得什么声音或气味吗？
- 那天的天气您还记得吗？

### 5. 追问情感和反思
- 现在回想起来，您怎么看待那段经历？
- 那件事教会了您什么？
- 您希望后辈从这个故事里学到什么？

## 对话风格
- 每次只问一个问题，等长辈说完再追问
- 先简短回应长辈说的内容（具体回应，不要泛泛说"真有意思"）
- 用"您"称呼，语气温和但不过分客套
- 如果长辈讲到动情处，安静倾听，不急着追问

## 开场方向参考
可以从这些话题切入：童年记忆、求学经历、工作生涯、婚姻家庭、人生转折点、最自豪的事、最遗憾的事、想对后辈说的话。""",
                    "speaking_style": "你说话温和但不啰嗦，每句话都有目的。回应时先具体提到长辈刚才说的内容，再自然地追问下一个有价值的问题。",
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

            payload = gzip.compress(json.dumps(session_config).encode())
            start_session_req = bytearray(generate_header())
            start_session_req.extend(int(100).to_bytes(4, 'big'))
            start_session_req.extend(len(self.session_id).to_bytes(4, 'big'))
            start_session_req.extend(self.session_id.encode())
            start_session_req.extend(len(payload).to_bytes(4, 'big'))
            start_session_req.extend(payload)
            await self.ws.send(start_session_req)
            response = await self.ws.recv()
            print(f"StartSession response: {parse_response(response)}")

            self.is_connected = True
            return True

        except Exception as e:
            print(f"[Doubao] 连接失败!")
            print(f"[Doubao] 错误类型: {type(e).__name__}")
            print(f"[Doubao] 错误信息: {e}")
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
            print(f"发送音频失败: {e}")

    async def say_hello(self, content: str = "您好！今天想听您讲讲您的故事。我特别想知道，您小时候住在哪里？那时候的生活是什么样的？") -> None:
        """发送开场白"""
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

                    # 提取文本内容
                    if isinstance(payload, dict):
                        # 从 results 数组中提取文本（事件 451 等）
                        results = payload.get('results', [])
                        if results and isinstance(results, list) and len(results) > 0:
                            result = results[0]
                            if isinstance(result, dict):
                                # AI 回复文本
                                response_text = result.get('text')
                                if response_text and self.on_text:
                                    self.on_text('response', response_text)

                                # ASR 文本
                                asr_text = result.get('asr_text')
                                if asr_text and self.on_text:
                                    self.on_text('asr', asr_text)

                        # 兼容其他格式
                        if not results:
                            response_text = payload.get('text') or payload.get('content')
                            if response_text and self.on_text:
                                self.on_text('response', response_text)

                            asr_text = payload.get('asr_text')
                            if asr_text and self.on_text:
                                self.on_text('asr', asr_text)

                    # 会话结束事件
                    if event in (152, 153):
                        print(f"会话结束: event={event}")
                        break

        except asyncio.CancelledError:
            print("接收循环已取消")
        except Exception as e:
            print(f"接收消息错误: {e}")
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
