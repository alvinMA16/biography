from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db, SessionLocal
from app.services.chat_service import chat_service
from app.services.llm_service import llm_service

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


class EmpathyRequest(BaseModel):
    text: str


class EmpathyResponse(BaseModel):
    response: str


@router.post("/empathy", response_model=EmpathyResponse)
def generate_empathy(request: EmpathyRequest):
    """生成共情回应（轻量级，不需要对话上下文）"""
    response = llm_service.generate_empathy(request.text)
    return EmpathyResponse(response=response)


@router.post("/{conversation_id}/end", response_model=ConversationResponse)
def end_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """结束对话"""
    conversation = chat_service.end_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conversation


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
