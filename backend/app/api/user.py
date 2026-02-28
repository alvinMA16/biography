from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.database import get_db
from app.models import User, Conversation, Message, Memoir
from app.auth import get_current_user

router = APIRouter()


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
    main_city: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    nickname: Optional[str]
    birth_year: Optional[int]
    hometown: Optional[str]
    main_city: Optional[str]
    profile_completed: bool


class EraMemoriesResponse(BaseModel):
    era_memories: Optional[str]
    era_memories_status: str = 'none'  # none / pending / generating / completed / failed
    birth_year: Optional[int]
    hometown: Optional[str]
    main_city: Optional[str]


@router.get("/me", response_model=UserResponse)
def get_user(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.put("/me/settings", response_model=UserResponse)
def update_settings(
    settings: UserSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新用户设置"""
    current_user.settings = settings.model_dump()
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/profile", response_model=UserProfileResponse)
def get_user_profile(current_user: User = Depends(get_current_user)):
    """获取用户基础信息（用于判断是否需要信息收集）"""
    return UserProfileResponse(
        nickname=current_user.nickname,
        birth_year=current_user.birth_year,
        hometown=current_user.hometown,
        main_city=current_user.main_city,
        profile_completed=current_user.profile_completed or False,
    )


@router.get("/me/era-memories", response_model=EraMemoriesResponse)
def get_era_memories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户的时代记忆"""
    user = current_user

    # 智能判断状态（兼容旧数据）
    status = user.era_memories_status or 'none'
    if status == 'none':
        if user.era_memories:
            status = 'completed'
            user.era_memories_status = 'completed'
            db.commit()
        elif user.birth_year:
            status = 'pending'
            user.era_memories_status = 'pending'
            db.commit()

    return EraMemoriesResponse(
        era_memories=user.era_memories,
        era_memories_status=status,
        birth_year=user.birth_year,
        hometown=user.hometown,
        main_city=user.main_city,
    )


@router.post("/me/era-memories/regenerate", response_model=EraMemoriesResponse)
def regenerate_era_memories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """重新生成时代记忆"""
    from app.services.profile_service import profile_service

    if not current_user.birth_year:
        raise HTTPException(status_code=400, detail="缺少出生年份信息")

    era_memories = profile_service.regenerate_era_memories(db, current_user.id)
    db.refresh(current_user)

    return EraMemoriesResponse(
        era_memories=era_memories,
        era_memories_status=current_user.era_memories_status or 'completed',
        birth_year=current_user.birth_year,
        hometown=current_user.hometown,
        main_city=current_user.main_city,
    )


@router.post("/me/complete-profile")
def complete_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """标记用户信息收集已完成"""
    current_user.profile_completed = True
    db.commit()
    return {"message": "已完成"}


@router.delete("/me")
def delete_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """注销用户账号，删除所有相关数据"""
    user_id = current_user.id

    db.query(Memoir).filter(Memoir.user_id == user_id).delete()

    conversations = db.query(Conversation).filter(Conversation.user_id == user_id).all()
    for conv in conversations:
        db.query(Message).filter(Message.conversation_id == conv.id).delete()

    db.query(Conversation).filter(Conversation.user_id == user_id).delete()

    db.delete(current_user)
    db.commit()

    return {"message": "账号已注销"}
