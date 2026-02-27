from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.database import get_db
from app.models import User
from app.services.topic_service import topic_service
from app.auth import get_current_user

router = APIRouter()


class TopicOption(BaseModel):
    id: str
    topic: str
    greeting: str
    context: str = ""


class TopicOptionsResponse(BaseModel):
    options: List[TopicOption]


@router.get("/options", response_model=TopicOptionsResponse)
def get_topic_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户的话题选项"""
    options = topic_service.get_topic_options(db, current_user.id)

    if not options:
        options = topic_service.generate_topic_options(db, current_user)

    return TopicOptionsResponse(
        options=[
            TopicOption(
                id=opt.get("id", ""),
                topic=opt["topic"],
                greeting=opt["greeting"],
                context=opt.get("context", ""),
            )
            for opt in options
        ]
    )


@router.post("/refresh", response_model=TopicOptionsResponse)
def refresh_topic_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """手动刷新用户的话题选项"""
    options = topic_service.generate_topic_options(db, current_user)

    return TopicOptionsResponse(
        options=[
            TopicOption(
                id=opt.get("id", ""),
                topic=opt["topic"],
                greeting=opt["greeting"],
                context=opt.get("context", ""),
            )
            for opt in options
        ]
    )


@router.get("/{topic_id}")
def get_topic(
    topic_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取单个话题详情"""
    topic = topic_service.get_topic_by_id(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="话题不存在")

    # ownership 校验
    if topic.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该话题")

    return {
        "id": topic.id,
        "topic": topic.topic,
        "greeting": topic.greeting,
        "context": topic.chat_context or "",
    }
