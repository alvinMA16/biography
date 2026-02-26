from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db, SessionLocal
from app.services.chat_service import chat_service
from app.services.llm_service import llm_service
from app.services.summary_service import summary_service
from app.services.greeting_service import greeting_service
from app.services.profile_service import profile_service
from app.models import Conversation, User

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str]
    topic: Optional[str]
    summary: Optional[str]
    status: str
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True


class StartResponse(BaseModel):
    conversation_id: str
    message: str


class ChatResponse(BaseModel):
    message: str


@router.post("/start", response_model=StartResponse)
def start_conversation(user_id: str, db: Session = Depends(get_db)):
    """开始新对话"""
    conversation, first_message = chat_service.start_conversation(db, user_id)
    return StartResponse(
        conversation_id=conversation.id,
        message=first_message
    )


@router.post("/{conversation_id}/chat", response_model=ChatResponse)
def chat(conversation_id: str, request: ChatRequest, db: Session = Depends(get_db)):
    """发送消息"""
    conversation = chat_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")

    if conversation.status == "completed":
        raise HTTPException(status_code=400, detail="对话已结束")

    response = chat_service.chat(db, conversation_id, request.message)
    return ChatResponse(message=response)


@router.post("/{conversation_id}/chat/stream")
def chat_stream(conversation_id: str, request: ChatRequest):
    """流式发送消息"""
    db = SessionLocal()
    try:
        conversation = chat_service.get_conversation(db, conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="对话不存在")

        if conversation.status == "completed":
            raise HTTPException(status_code=400, detail="对话已结束")

        def generate():
            try:
                for chunk in chat_service.chat_stream(db, conversation_id, request.message):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"
            finally:
                db.close()

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        db.close()
        raise e


@router.post("/{conversation_id}/end", response_model=ConversationResponse)
def end_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """结束对话（生成摘要）"""
    conversation = chat_service.end_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation


def process_conversation_end(conversation_id: str, user_id: str):
    """后台处理对话结束后的任务"""
    db = SessionLocal()
    try:
        print(f"[Conversation] 开始处理对话结束任务: {conversation_id}")

        # 检查用户是否完成了信息收集
        user = db.query(User).filter(User.id == user_id).first()

        if user and not user.profile_completed:
            # 用户未完成信息收集，尝试从对话中提取信息
            print(f"[Conversation] 用户未完成信息收集，尝试提取...")
            profile_service.extract_and_update_profile(db, conversation_id, user_id)
            # 如果信息收集完成，generate_initial_greetings 会在 profile_service 中被调用
        else:
            # 正常对话结束流程
            # 1. 生成对话摘要
            summary_service.generate_summary(db, conversation_id)

            # 2. 刷新用户的开场白池
            greeting_service.refresh_greetings(db, user_id)

        print(f"[Conversation] 对话结束任务完成: {conversation_id}")
    except Exception as e:
        print(f"[Conversation] 对话结束任务失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@router.post("/{conversation_id}/end-quick")
def end_conversation_quick(
    conversation_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """快速结束对话（后台生成摘要和刷新开场白）"""
    conversation = chat_service.end_conversation_quick(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")

    # 后台任务：生成摘要、刷新开场白
    background_tasks.add_task(
        process_conversation_end,
        conversation_id,
        conversation.user_id
    )

    return {"status": "ok", "conversation_id": conversation_id}


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """获取对话详情"""
    conversation = chat_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation


@router.get("/user/{user_id}/list")
def list_conversations(user_id: str, db: Session = Depends(get_db)):
    """获取用户的对话列表"""
    conversations = chat_service.get_user_conversations(db, user_id)
    return [
        {
            "id": c.id,
            "title": c.title,
            "summary": c.summary,
            "status": c.status,
            "created_at": c.created_at.isoformat()
        }
        for c in conversations
    ]
