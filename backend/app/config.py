from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 数据库配置
    database_url: str = "sqlite:///./biography.db"

    # 通义千问 API配置
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen-plus"

    # 阿里云语音识别配置
    aliyun_ak_id: str = ""
    aliyun_ak_secret: str = ""
    aliyun_nls_appkey: str = ""

    # 应用配置
    debug: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
