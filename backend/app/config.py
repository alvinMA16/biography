from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 数据库配置
    database_url: str = "sqlite:///./biography.db"

    # 通义千问 API配置（备用）
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen-plus"
    dashscope_model_fast: str = "qwen-turbo"

    # 阿里云语音识别配置（备用）
    aliyun_ak_id: str = ""
    aliyun_ak_secret: str = ""
    aliyun_nls_appkey: str = ""

    # 豆包实时对话配置
    doubao_app_id: str = ""
    doubao_access_key: str = ""
    doubao_ws_url: str = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"
    doubao_speaker: str = "zh_female_xiaohe_jupiter_bigtts"  # 发音人

    # 应用配置
    debug: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
