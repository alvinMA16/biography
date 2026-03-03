from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.database import get_db
from app.models import User, Conversation, Message, Memoir, WelcomeMessage, AuditLog
from app.auth import get_current_user, verify_password, hash_password

router = APIRouter()


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


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
    preferred_name: Optional[str]
    gender: Optional[str]
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


@router.post("/me/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改密码"""
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码不正确")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少需要6位")
    current_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}


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
        preferred_name=current_user.preferred_name,
        gender=current_user.gender,
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


@router.get("/welcome-messages")
def get_welcome_messages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取启用的激励语列表"""
    messages = db.query(WelcomeMessage).filter(
        WelcomeMessage.is_active == True
    ).order_by(WelcomeMessage.sort_order.asc()).all()
    return [{"id": m.id, "content": m.content, "show_greeting": m.show_greeting} for m in messages]


@router.get("/me/export")
def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """导出用户的所有数据（个人信息、对话记录、回忆录）"""
    user_id = current_user.id

    # 用户基本信息
    profile = {
        "nickname": current_user.nickname,
        "preferred_name": current_user.preferred_name,
        "gender": current_user.gender,
        "birth_year": current_user.birth_year,
        "hometown": current_user.hometown,
        "main_city": current_user.main_city,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }

    # 对话记录（含消息）
    conversations = db.query(Conversation).filter(
        Conversation.user_id == user_id,
        Conversation.deleted_at == None,
    ).order_by(Conversation.created_at).all()

    conversations_data = []
    for conv in conversations:
        messages = db.query(Message).filter(
            Message.conversation_id == conv.id
        ).order_by(Message.created_at).all()

        conversations_data.append({
            "title": conv.title,
            "topic": conv.topic,
            "summary": conv.summary,
            "status": conv.status,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in messages
            ],
        })

    # 回忆录
    memoirs = db.query(Memoir).filter(
        Memoir.user_id == user_id,
        Memoir.deleted_at == None,
    ).order_by(Memoir.order_index).all()

    memoirs_data = [
        {
            "title": m.title,
            "content": m.content,
            "year_start": m.year_start,
            "year_end": m.year_end,
            "time_period": m.time_period,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in memoirs
    ]

    return JSONResponse(content={
        "profile": profile,
        "conversations": conversations_data,
        "memoirs": memoirs_data,
    })


@router.delete("/me")
def delete_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """注销用户账号（软删除，数据保留 30 天后可由管理员清理）"""
    user_id = current_user.id
    now = datetime.utcnow()

    # 软删除用户
    current_user.deleted_at = now
    current_user.is_active = False

    # 级联软删除关联数据
    db.query(Conversation).filter(
        Conversation.user_id == user_id,
        Conversation.deleted_at == None,
    ).update({"deleted_at": now})
    db.query(Memoir).filter(
        Memoir.user_id == user_id,
        Memoir.deleted_at == None,
    ).update({"deleted_at": now})

    # 记录审计日志
    audit = AuditLog(
        action="delete_user",
        target_user_id=user_id,
        target_label=current_user.phone or current_user.nickname,
        detail="用户自助注销账号（软删除）",
    )
    db.add(audit)

    db.commit()

    return {"message": "账号已注销"}
