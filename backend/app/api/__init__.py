from fastapi import APIRouter
from app.api import user, conversation, memoir, asr

router = APIRouter()

router.include_router(user.router, prefix="/user", tags=["用户"])
router.include_router(conversation.router, prefix="/conversation", tags=["对话"])
router.include_router(memoir.router, prefix="/memoir", tags=["回忆录"])
router.include_router(asr.router, prefix="/asr", tags=["语音识别"])
