from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.database import get_db
from app.models import User

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

    class Config:
        from_attributes = True


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
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/{user_id}/settings", response_model=UserResponse)
def update_settings(user_id: str, settings: UserSettings, db: Session = Depends(get_db)):
    """更新用户设置"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="用户不存在")

    user.settings = settings.model_dump()
    db.commit()
    db.refresh(user)
    return user
