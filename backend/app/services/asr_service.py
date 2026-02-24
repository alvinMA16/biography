import json
import time
import httpx
from typing import Optional
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from app.config import settings


class ASRService:
    def __init__(self):
        self.client = AcsClient(
            settings.aliyun_ak_id,
            settings.aliyun_ak_secret,
            "cn-shanghai"
        )
        self.appkey = settings.aliyun_nls_appkey
        self.token: Optional[str] = None
        self.token_expire_time: int = 0

    def get_token(self) -> str:
        """获取或刷新 Token"""
        current_time = int(time.time())

        # 如果 token 还有效（提前5分钟刷新）
        if self.token and self.token_expire_time > current_time + 300:
            return self.token

        # 重新获取 token
        request = CommonRequest()
        request.set_method('POST')
        request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
        request.set_version('2019-02-28')
        request.set_action_name('CreateToken')

        response = self.client.do_action_with_exception(request)
        result = json.loads(response)

        if 'Token' in result and 'Id' in result['Token']:
            self.token = result['Token']['Id']
            self.token_expire_time = result['Token']['ExpireTime']
            return self.token
        else:
            raise Exception("获取 Token 失败")

    async def recognize(self, audio_data: bytes) -> str:
        """
        识别语音
        :param audio_data: 音频数据 (PCM 16bit 16kHz 单声道)
        :return: 识别结果文本
        """
        token = self.get_token()

        url = f"http://nls-gateway-cn-shanghai.aliyuncs.com/stream/v1/asr?appkey={self.appkey}"

        headers = {
            "X-NLS-Token": token,
            "Content-Type": "application/octet-stream"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, content=audio_data, timeout=30.0)
            result = response.json()

            if result.get("status") == 20000000:
                return result.get("result", "")
            else:
                raise Exception(f"语音识别失败: {result.get('message', '未知错误')}")


asr_service = ASRService()
