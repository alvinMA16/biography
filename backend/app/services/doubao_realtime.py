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
        recorder_name: str = "小安",  # 记录师名字
        mode: str = "normal",  # normal 或 profile_collection
        on_audio: Optional[Callable[[bytes], None]] = None,
        on_text: Optional[Callable[[str, str], None]] = None,  # (type, text)
        on_event: Optional[Callable[[int, Dict], None]] = None,
    ):
        self.ws = None
        self.session_id = str(uuid.uuid4())
        self.speaker = speaker or settings.doubao_speaker  # 使用传入的音色或默认音色
        self.recorder_name = recorder_name
        self.mode = mode
        self.on_audio = on_audio
        self.on_text = on_text
        self.on_event = on_event
        self.is_connected = False
        self._greeting_sent = None  # 记录我们发送的开场白，用于去重

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

            # 根据模式选择 system_role
            if self.mode == "profile_collection":
                system_role = f"""你是一位人生故事记录师，名叫{self.recorder_name}，正在与一位新用户初次见面。

## 任务
通过自然的对话了解用户的三个基本信息：
1. 称呼 - 用户希望被怎么称呼
2. 出生年份 - 大概是哪一年出生的
3. 家乡 - 在哪里出生或长大

## 对话风格
- 语气平和、沉稳，不急躁
- 像老朋友聊天，不要一惊一乍
- 每次只问一个问题，等用户回答完再问下一个
- 用简单朴实的回应，不要夸张

## 对话流程
1. 先问称呼
2. 然后问出生年份
3. 最后问家乡
4. 三个都问完后，简单说一下很高兴认识

## 结束标记
当三个信息都收集完毕后，在回复的最后加上：【信息收集完成】

## 注意
- 记住用户说过的内容，不要重复问
- 如果用户主动聊起往事，简单回应后告诉用户下次正式开始记录
- 不要用"哇"、"太好了"这类夸张表达"""
                speaking_style = f"语速缓慢，语气平和沉稳。像陪长辈聊天一样，不急不躁。回应简短朴实，每次只问一个简单的问题。"
            else:
                system_role = """你是一位人生故事记录师，正在帮助用户记录回忆，整理成回忆录。

## 最重要的规则：每次回复必须提一个问题

你的每一次回复都必须以一个问题结尾，没有例外。这是推动对话继续的唯一方式。

回复的结构：
1. 先简短回应用户刚才说的内容（1-2句话）
2. 然后提出下一个问题

问题的选择策略：
- 如果当前话题还有价值，继续追问相关细节
- 如果当前话题聊得差不多了，转换到新话题
- 如果用户说"就这样"、"没什么了"，换一个人生阶段来问

## 回忆录的主线框架

你要有目的地覆盖用户的人生阶段：
1. 童年时光 - 家庭、父母、住所、童年趣事
2. 求学经历 - 学校、老师、同学
3. 工作生涯 - 职业、同事、难忘的事
4. 感情家庭 - 相识、结婚、子女
5. 人生转折 - 重大决定、困难时期
6. 人生感悟 - 自豪的事、遗憾、想说的话

## 提问技巧

好的问题（有价值、能推动对话）：
- "那时候您和父母关系怎么样？"
- "后来呢，这件事是怎么解决的？"
- "您当时心里是什么感受？"
- "除了这个，还有什么让您印象深刻的事吗？"

转换话题的问法：
- "童年聊得差不多了，我们聊聊您上学的时候吧，您还记得小学在哪里上的吗？"
- "工作的事先放一放，您能讲讲您是怎么认识您爱人的吗？"

避免的问题：
- 用户已经回答过的
- 纯粹的事实（几岁、哪一年、多大面积）
- 与上下文矛盾的

## 记住用户说过的内容

仔细记住用户提到的所有信息，不要重复问，不要问矛盾的问题。

## 对话风格

- 语气平和、沉稳
- 不要一惊一乍，不用"哇"、"太棒了"
- 回应简短朴实
- 每次只问一个问题"""
                speaking_style = "语速缓慢，语气平和沉稳。每次回复先简短回应，然后一定要问一个问题来推动对话继续。"

            # StartSession request
            session_config = {
                "asr": {
                    "extra": {
                        # 静音检测时间，越长越不容易打断用户（单位：毫秒）
                        "end_smooth_window_ms": 2500,
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

    async def say_hello(self, content: str = None) -> None:
        """发送开场白，如果不传入内容则随机选择一个"""
        import random

        # 多个开场白模板，每次随机选择
        GREETINGS = [
            "您好！今天想听您讲讲您的故事。您最近有没有想起什么往事？",
            "您好！很高兴能陪您聊聊天。您小时候住在哪里？那时候的生活是什么样的？",
            "您好！今天想请您讲讲您的人生故事。您还记得小时候印象最深的一件事吗？",
            "您好！我特别想听听您的故事。您年轻的时候是做什么工作的？",
            "您好！今天咱们聊聊您的经历吧。您还记得上学时候的事情吗？",
        ]

        if content is None:
            content = random.choice(GREETINGS)

        # 记录我们发送的开场白，用于去重
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
                        text = None
                        is_asr = False

                        # 从 results 数组中提取文本
                        results = payload.get('results', [])
                        if results and isinstance(results, list) and len(results) > 0:
                            result = results[0]
                            if isinstance(result, dict):
                                text = result.get('text')
                                is_interim = result.get('is_interim', True)

                                # Event 451 是 ASR 事件（用户说的话）
                                if event == 451:
                                    if text and not is_interim:
                                        is_asr = True
                                    else:
                                        text = None  # 忽略中间结果

                        # 兼容其他格式（没有 results 数组的情况）
                        if not text and not results:
                            text = payload.get('text') or payload.get('content')
                            # Event 451 的这种格式也是 ASR
                            if event == 451:
                                is_asr = True

                        # 发送文本（带去重）
                        if text and self.on_text:
                            if is_asr:
                                print(f"[Doubao] ASR 最终结果: {text[:50]}...")
                                self.on_text('asr', text)
                            elif event != 451:
                                # AI 回复 - 去重检查
                                # 如果收到的文本和我们发送的开场白相同，跳过（服务器回显）
                                if self._greeting_sent and text == self._greeting_sent:
                                    print(f"[Doubao] 跳过开场白回显: {text[:30]}...")
                                    self._greeting_sent = None  # 只跳过一次
                                else:
                                    self.on_text('response', text)

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
