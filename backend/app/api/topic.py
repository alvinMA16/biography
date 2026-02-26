from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import User
from app.services.topic_service import topic_service

router = APIRouter()


class TopicOption(BaseModel):
    id: str
    topic: str
    greeting: str
    context: str = ""


class TopicOptionsResponse(BaseModel):
    options: List[TopicOption]


@router.get("/user/{user_id}/options", response_model=TopicOptionsResponse)
def get_topic_options(user_id: str, db: Session = Depends(get_db)):
    """获取用户的话题选项"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    options = topic_service.get_topic_options(db, user_id)

    # 如果没有话题选项，生成一些
    if not options:
        options = topic_service.generate_topic_options(db, user)

    return TopicOptionsResponse(
        options=[TopicOption(id=opt.get("id", ""), topic=opt["topic"], greeting=opt["greeting"], context=opt.get("context", "")) for opt in options]
    )


@router.post("/user/{user_id}/refresh", response_model=TopicOptionsResponse)
def refresh_topic_options(user_id: str, db: Session = Depends(get_db)):
    """手动刷新用户的话题选项"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    options = topic_service.generate_topic_options(db, user)

    return TopicOptionsResponse(
        options=[TopicOption(id=opt.get("id", ""), topic=opt["topic"], greeting=opt["greeting"], context=opt.get("context", "")) for opt in options]
    )


@router.get("/{topic_id}")
def get_topic(topic_id: str, db: Session = Depends(get_db)):
    """获取单个话题详情"""
    topic = topic_service.get_topic_by_id(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="话题不存在")

    return {
        "id": topic.id,
        "topic": topic.topic,
        "greeting": topic.greeting,
        "context": topic.chat_context or ""
    }
