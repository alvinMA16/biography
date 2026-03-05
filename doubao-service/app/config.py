from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 豆包实时对话配置
    doubao_app_id: str = ""
    doubao_access_key: str = ""
    doubao_ws_url: str = "wss://openspeech.bytedance.com/api/v3/realtime/dialogue"
    doubao_speaker: str = "zh_female_xiaohe_jupiter_bigtts"
    doubao_asr_silence_ms: int = 4000

    class Config:
        env_file = ".env"


settings = Settings()
