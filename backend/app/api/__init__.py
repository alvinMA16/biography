from fastapi import APIRouter
from app.api import user, conversation, memoir, asr, realtime, topic, auth

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(auth.admin_router, prefix="/admin", tags=["管理员"])
router.include_router(user.router, prefix="/user", tags=["用户"])
router.include_router(conversation.router, prefix="/conversation", tags=["对话"])
router.include_router(memoir.router, prefix="/memoir", tags=["回忆录"])
router.include_router(asr.router, prefix="/asr", tags=["语音识别"])
router.include_router(realtime.router, prefix="/realtime", tags=["实时对话"])
router.include_router(topic.router, prefix="/topic", tags=["话题"])
