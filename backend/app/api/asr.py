from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from app.services.asr_service import asr_service

router = APIRouter()


class ASRResponse(BaseModel):
    text: str


@router.post("/recognize", response_model=ASRResponse)
async def recognize_speech(file: UploadFile = File(...)):
    """
    语音识别接口
    接收音频文件，返回识别结果
    音频要求：PCM 16bit 16kHz 单声道，或 WAV 格式
    """
    try:
        audio_data = await file.read()
        text = await asr_service.recognize(audio_data)
        return ASRResponse(text=text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
