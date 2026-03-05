from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 数据库配置
    database_url: str = "sqlite:///./biography.db"

    # 通义千问 API配置（备用）
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen3.5-plus"
    dashscope_model_fast: str = "qwen-turbo"

    # 阿里云语音识别配置（备用）
    aliyun_ak_id: str = ""
    aliyun_ak_secret: str = ""
    aliyun_nls_appkey: str = ""

    # 豆包实时对话配置（通过 Doubao Service 微服务代理）
    doubao_service_url: str = "ws://localhost:9000/ws"  # Doubao Service WebSocket 地址
    doubao_speaker: str = "zh_female_xiaohe_jupiter_bigtts"  # 发音人（用于前端展示）

    # 认证配置
    jwt_secret: str = "change-me-in-production"
    jwt_expire_days: int = 30
    admin_api_key: str = ""

    # 应用配置
    debug: bool = True
    service_region: str = "CN"  # 服务区域：CN=中国大陆（使用预生成时代记忆），其他=临时生成

    # 话题生成配置
    topic_option_count: int = 4   # 首次生成的话题选项数量

    # 增强模式 - 干预相关配置
    intervention_enabled: bool = True           # 是否启用干预
    intervention_timeout_ms: int = 6000         # 干预判断超时（毫秒）- TTS结束后的沉默间隙执行
    intervention_model: str = "qwen-turbo"      # 干预判断用的模型（需要快，qwen3.5-plus太慢会超时）

    # LLM Provider 路由
    llm_provider_default: str = "dashscope"     # 全局默认 provider

    # 模块级 override（空串 = 用全局默认）
    llm_provider_memoir: str = ""
    llm_provider_summary: str = ""
    llm_provider_topic: str = ""
    llm_provider_profile: str = ""
    llm_provider_intervention: str = ""

    # Gemini Provider（原生 SDK 直连）
    gemini_api_key: str = ""
    gemini_sock5_proxy: str = ""   # 同步调用代理（支持 socks5），如 socks5://127.0.0.1:1080
    gemini_http_proxy: str = ""    # 异步调用代理（不支持 socks5），如 http://127.0.0.1:8118
    gemini_model: str = "gemini-2.5-flash"
    gemini_model_fast: str = "gemini-2.0-flash-lite"

    class Config:
        env_file = ".env"


settings = Settings()
