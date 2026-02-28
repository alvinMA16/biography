"""认证相关路由：登录、管理员创建用户、用户管理"""
import logging
import secrets
import string
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import User, TopicCandidate
from app.models.conversation import Conversation, Message
from app.models.memoir import Memoir
from app.models.audit_log import AuditLog
from app.auth import hash_password, verify_password, create_token, verify_admin_key

logger = logging.getLogger(__name__)


def _log_action(db: Session, action: str, target_user_id: str = None, target_label: str = None, detail: str = None):
    """记录管理员操作日志"""
    log = AuditLog(action=action, target_user_id=target_user_id, target_label=target_label, detail=detail)
    db.add(log)
    db.commit()

def _run_post_profile_tasks(user_id: str):
    """后台任务：为 profile 已完成的用户生成开场白和话题"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning("[Admin] 后台任务：用户 %s 不存在，跳过", user_id)
            return

        from app.services.topic_service import topic_service

        logger.info("[Admin] 为用户 %s 生成初始话题...", user_id)
        topic_service.generate_topic_options(db, user)

        logger.info("[Admin] 用户 %s 的开场白和话题生成完成", user_id)
    except Exception as e:
        logger.error("[Admin] 为用户 %s 生成开场白/话题失败: %s", user_id, e)
        import traceback
        traceback.print_exc()
    finally:
        db.close()


router = APIRouter()


# ========== 登录 ==========

class LoginRequest(BaseModel):
    phone: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """手机号 + 密码登录"""
    user = db.query(User).filter(User.phone == req.phone).first()
    if not user:
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    if not user.password_hash:
        raise HTTPException(status_code=401, detail="该账号未设置密码")
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="该账号已被禁用")

    token = create_token(user.id)
    return LoginResponse(
        token=token,
        user={
            "id": user.id,
            "nickname": user.nickname,
            "phone": user.phone,
            "profile_completed": user.profile_completed or False,
        },
    )


# ========== 管理员接口 ==========

class AdminCreateUserRequest(BaseModel):
    phone: str
    password: str
    nickname: Optional[str] = None
    birth_year: Optional[int] = None
    hometown: Optional[str] = None
    main_city: Optional[str] = None


class AdminCreateUserResponse(BaseModel):
    user_id: str
    phone: str


admin_router = APIRouter()


@admin_router.post("/user", response_model=AdminCreateUserResponse)
def admin_create_user(
    req: AdminCreateUserRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员创建用户"""
    # 检查手机号是否已存在
    existing = db.query(User).filter(User.phone == req.phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="该手机号已注册")

    user = User(
        phone=req.phone,
        password_hash=hash_password(req.password),
        nickname=req.nickname,
        birth_year=req.birth_year,
        hometown=req.hometown,
        main_city=req.main_city,
    )
    # 如果基础信息齐全，自动标记 profile_completed
    if req.nickname and req.birth_year and req.hometown:
        user.profile_completed = True

    db.add(user)
    db.commit()
    db.refresh(user)

    _log_action(db, "create_user", user.id, user.phone,
                f"创建用户 {user.phone}" + (f"（{user.nickname}）" if user.nickname else ""))

    # 如果 profile 已完成，后台生成开场白和话题
    if user.profile_completed:
        background_tasks.add_task(_run_post_profile_tasks, user.id)

    return AdminCreateUserResponse(user_id=user.id, phone=user.phone)


# ========== 管理员：用户列表 ==========

class AdminUserItem(BaseModel):
    id: str
    phone: Optional[str] = None
    nickname: Optional[str] = None
    birth_year: Optional[int] = None
    hometown: Optional[str] = None
    main_city: Optional[str] = None
    profile_completed: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    conversation_count: int = 0
    memoir_count: int = 0


@admin_router.get("/users", response_model=List[AdminUserItem])
def admin_list_users(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员获取所有用户列表"""
    users = db.query(User).order_by(User.created_at.desc()).all()

    # 批量查询对话和回忆录计数
    conv_counts = dict(
        db.query(Conversation.user_id, func.count(Conversation.id))
        .group_by(Conversation.user_id)
        .all()
    )
    memoir_counts = dict(
        db.query(Memoir.user_id, func.count(Memoir.id))
        .group_by(Memoir.user_id)
        .all()
    )

    return [
        AdminUserItem(
            id=u.id,
            phone=u.phone,
            nickname=u.nickname,
            birth_year=u.birth_year,
            hometown=u.hometown,
            main_city=u.main_city,
            profile_completed=u.profile_completed or False,
            is_active=u.is_active if u.is_active is not None else True,
            created_at=u.created_at,
            conversation_count=conv_counts.get(u.id, 0),
            memoir_count=memoir_counts.get(u.id, 0),
        )
        for u in users
    ]


# ========== 管理员：编辑用户 ==========

class AdminUpdateUserRequest(BaseModel):
    nickname: Optional[str] = None
    birth_year: Optional[int] = None
    hometown: Optional[str] = None
    main_city: Optional[str] = None


@admin_router.put("/user/{user_id}")
def admin_update_user(
    user_id: str,
    req: AdminUpdateUserRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员编辑用户基础信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    was_profile_completed = user.profile_completed or False

    if req.nickname is not None:
        user.nickname = req.nickname
    if req.birth_year is not None:
        user.birth_year = req.birth_year
    if req.hometown is not None:
        user.hometown = req.hometown
    if req.main_city is not None:
        user.main_city = req.main_city

    # 自动判断 profile_completed
    if user.nickname and user.birth_year and user.hometown:
        user.profile_completed = True

    db.commit()
    db.refresh(user)

    _log_action(db, "edit_user", user.id, user.phone or user.nickname,
                f"编辑用户信息：{user.phone or user.nickname}")

    # 如果 profile 从未完成变为完成，后台生成开场白和话题
    if not was_profile_completed and user.profile_completed:
        background_tasks.add_task(_run_post_profile_tasks, user.id)

    return {
        "id": user.id,
        "nickname": user.nickname,
        "birth_year": user.birth_year,
        "hometown": user.hometown,
        "main_city": user.main_city,
        "profile_completed": user.profile_completed or False,
    }


# ========== 管理员：重置密码 ==========

class ResetPasswordResponse(BaseModel):
    user_id: str
    new_password: str


@admin_router.post("/user/{user_id}/reset-password", response_model=ResetPasswordResponse)
def admin_reset_password(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员重置用户密码，返回随机新密码"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 生成 8 位随机密码
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for _ in range(8))

    user.password_hash = hash_password(new_password)
    db.commit()

    _log_action(db, "reset_password", user.id, user.phone or user.nickname,
                f"重置密码：{user.phone or user.nickname}")

    return ResetPasswordResponse(user_id=user.id, new_password=new_password)


# ========== 管理员：删除用户 ==========


@admin_router.delete("/user/{user_id}")
def admin_delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员硬删除用户及所有关联数据"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user_label = user.phone or user.nickname or user_id

    # 手动删除关联数据（Conversation/Memoir 没有配置 cascade delete）
    # 1. 删除回忆录
    db.query(Memoir).filter(Memoir.user_id == user_id).delete()
    # 2. 删除消息（通过对话关联）
    conv_ids = [c.id for c in db.query(Conversation.id).filter(Conversation.user_id == user_id).all()]
    if conv_ids:
        db.query(Message).filter(Message.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
    # 3. 删除对话
    db.query(Conversation).filter(Conversation.user_id == user_id).delete()
    # 4. 话题候选（有 cascade，但显式删除更安全）
    db.query(TopicCandidate).filter(TopicCandidate.user_id == user_id).delete()
    # 5. 删除用户
    db.delete(user)
    db.commit()

    _log_action(db, "delete_user", user_id, user_label, f"删除用户 {user_label} 及所有关联数据")

    logger.info("[Admin] 已删除用户 %s（%s）及所有关联数据", user_id, user_label)
    return {"success": True}


# ========== 管理员：禁用/启用用户 ==========


@admin_router.post("/user/{user_id}/toggle-active")
def admin_toggle_user_active(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员切换用户禁用/启用状态"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)

    status_text = "启用" if user.is_active else "禁用"
    user_label = user.phone or user.nickname or user_id
    _log_action(db, "toggle_user_active", user.id, user_label, f"{status_text}用户 {user_label}")

    logger.info("[Admin] 已%s用户 %s（%s）", status_text, user_id, user_label)
    return {"user_id": user.id, "is_active": user.is_active}


# ========== 管理员：操作日志 ==========

class AuditLogItem(BaseModel):
    id: str
    action: str
    target_label: Optional[str] = None
    detail: Optional[str] = None
    created_at: Optional[datetime] = None


@admin_router.get("/logs", response_model=List[AuditLogItem])
def admin_list_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员获取操作日志"""
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        AuditLogItem(
            id=log.id,
            action=log.action,
            target_label=log.target_label,
            detail=log.detail,
            created_at=log.created_at,
        )
        for log in logs
    ]


# ========== 管理员：时代记忆管理 ==========

class EraMemoryItem(BaseModel):
    id: str
    start_year: int
    end_year: int
    category: Optional[str] = None
    content: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EraMemoryCreateRequest(BaseModel):
    start_year: int
    end_year: int
    category: Optional[str] = None
    content: str


class EraMemoryUpdateRequest(BaseModel):
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    category: Optional[str] = None
    content: Optional[str] = None


@admin_router.get("/era-memories", response_model=List[EraMemoryItem])
def admin_list_era_memories(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员获取所有预生成的时代记忆"""
    from app.services.era_memory_service import era_memory_service
    memories = era_memory_service.get_all(db)
    return [
        EraMemoryItem(
            id=m.id,
            start_year=m.start_year,
            end_year=m.end_year,
            category=m.category,
            content=m.content,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in memories
    ]


@admin_router.post("/era-memories", response_model=EraMemoryItem)
def admin_create_era_memory(
    req: EraMemoryCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员创建时代记忆条目"""
    from app.services.era_memory_service import era_memory_service
    memory = era_memory_service.create(
        db,
        start_year=req.start_year,
        end_year=req.end_year,
        content=req.content,
        category=req.category
    )
    _log_action(db, "create_era_memory", None, f"{req.start_year}-{req.end_year}",
                f"创建时代记忆：{req.content[:50]}...")
    return EraMemoryItem(
        id=memory.id,
        start_year=memory.start_year,
        end_year=memory.end_year,
        category=memory.category,
        content=memory.content,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@admin_router.put("/era-memories/{memory_id}", response_model=EraMemoryItem)
def admin_update_era_memory(
    memory_id: str,
    req: EraMemoryUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员更新时代记忆条目"""
    from app.services.era_memory_service import era_memory_service
    memory = era_memory_service.update(
        db,
        memory_id=memory_id,
        start_year=req.start_year,
        end_year=req.end_year,
        content=req.content,
        category=req.category
    )
    if not memory:
        raise HTTPException(status_code=404, detail="时代记忆不存在")

    _log_action(db, "update_era_memory", None, f"{memory.start_year}-{memory.end_year}",
                f"更新时代记忆：{memory.content[:50]}...")
    return EraMemoryItem(
        id=memory.id,
        start_year=memory.start_year,
        end_year=memory.end_year,
        category=memory.category,
        content=memory.content,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@admin_router.delete("/era-memories/{memory_id}")
def admin_delete_era_memory(
    memory_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员删除时代记忆条目"""
    from app.services.era_memory_service import era_memory_service
    memory = era_memory_service.get_by_id(db, memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="时代记忆不存在")

    content_preview = memory.content[:50] if memory.content else ""
    year_range = f"{memory.start_year}-{memory.end_year}"

    era_memory_service.delete(db, memory_id)
    _log_action(db, "delete_era_memory", None, year_range,
                f"删除时代记忆：{content_preview}...")
    return {"success": True}
