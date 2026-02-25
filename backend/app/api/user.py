from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.database import get_db
from app.models import User, Conversation, Message, Memoir, GreetingCandidate

router = APIRouter()


class UserCreate(BaseModel):
    nickname: Optional[str] = None


class UserSettings(BaseModel):
    perspective: Optional[str] = "第一人称"  # 第一人称 or 第三人称
    topic_preference: Optional[str] = None  # 话题偏好


class UserResponse(BaseModel):
    id: str
    nickname: Optional[str]
    settings: Dict[str, Any]
    profile_completed: bool = False
    birth_year: Optional[int] = None
    hometown: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    nickname: Optional[str]
    birth_year: Optional[int]
    hometown: Optional[str]
    profile_completed: bool


@router.post("/create", response_model=UserResponse)
def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """创建新用户（体验版简化，无需微信登录）"""
    user = User(nickname=user_data.nickname)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: str, db: Session = Depends(get_db)):
    """获取用户信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/{user_id}/settings", response_model=UserResponse)
def update_settings(user_id: str, settings: UserSettings, db: Session = Depends(get_db)):
    """更新用户设置"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.settings = settings.model_dump()
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(user_id: str, db: Session = Depends(get_db)):
    """获取用户基础信息（用于判断是否需要信息收集）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    return UserProfileResponse(
        nickname=user.nickname,
        birth_year=user.birth_year,
        hometown=user.hometown,
        profile_completed=user.profile_completed or False
    )


@router.delete("/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db)):
    """注销用户账号，删除所有相关数据"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 删除用户的所有回忆录
    db.query(Memoir).filter(Memoir.user_id == user_id).delete()

    # 删除用户的所有对话消息
    conversations = db.query(Conversation).filter(Conversation.user_id == user_id).all()
    for conv in conversations:
        db.query(Message).filter(Message.conversation_id == conv.id).delete()

    # 删除用户的所有对话
    db.query(Conversation).filter(Conversation.user_id == user_id).delete()

    # 删除用户的开场白候选
    db.query(GreetingCandidate).filter(GreetingCandidate.user_id == user_id).delete()

    # 删除用户
    db.delete(user)
    db.commit()

    return {"message": "账号已注销"}
