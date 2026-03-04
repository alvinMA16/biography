"""认证相关路由：登录、管理员创建用户、用户管理"""
import logging
import secrets
import string
import time
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, TopicCandidate, WelcomeMessage, PresetTopic
from app.models.conversation import Conversation, Message
from app.models.memoir import Memoir
from app.models.audit_log import AuditLog
from app.auth import hash_password, verify_password, create_token, verify_admin_key
from app.services.profile_service import auto_set_preferred_name

logger = logging.getLogger(__name__)


def _log_action(db: Session, action: str, target_user_id: str = None, target_label: str = None, detail: str = None):
    """记录管理员操作日志"""
    log = AuditLog(action=action, target_user_id=target_user_id, target_label=target_label, detail=detail)
    db.add(log)
    db.commit()

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
    nickname: str  # 姓名（必填）
    gender: str  # 性别（必填：男/女）
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
        gender=req.gender,
        birth_year=req.birth_year,
        hometown=req.hometown,
        main_city=req.main_city,
    )
    # 如果基础信息齐全，自动标记 profile_completed
    if req.nickname and req.birth_year and req.hometown:
        user.profile_completed = True

    db.add(user)
    auto_set_preferred_name(user)
    db.commit()
    db.refresh(user)

    _log_action(db, "create_user", user.id, user.phone,
                f"创建用户 {user.phone}" + (f"（{user.nickname}）" if user.nickname else ""))

    return AdminCreateUserResponse(user_id=user.id, phone=user.phone)


# ========== 管理员：用户列表 ==========

class AdminUserItem(BaseModel):
    id: str
    phone: Optional[str] = None
    nickname: Optional[str] = None
    gender: Optional[str] = None
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
            gender=u.gender,
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
    gender: Optional[str] = None
    birth_year: Optional[int] = None
    hometown: Optional[str] = None
    main_city: Optional[str] = None


@admin_router.put("/user/{user_id}")
def admin_update_user(
    user_id: str,
    req: AdminUpdateUserRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员编辑用户基础信息"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if req.nickname is not None:
        user.nickname = req.nickname
    if req.gender is not None:
        user.gender = req.gender
    if req.birth_year is not None:
        user.birth_year = req.birth_year
    if req.hometown is not None:
        user.hometown = req.hometown
    if req.main_city is not None:
        user.main_city = req.main_city

    # 自动判断 profile_completed
    if user.nickname and user.birth_year and user.hometown:
        user.profile_completed = True

    auto_set_preferred_name(user)
    db.commit()
    db.refresh(user)

    _log_action(db, "edit_user", user.id, user.phone or user.nickname,
                f"编辑用户信息：{user.phone or user.nickname}")

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


# ========== 管理员：获取用户详情 ==========


class AdminMemoirDetailItem(BaseModel):
    id: str
    title: str
    content: Optional[str] = None
    status: str
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    time_period: Optional[str] = None
    conversation_id: Optional[str] = None
    conversation_start: Optional[str] = None
    conversation_end: Optional[str] = None
    created_at: Optional[datetime] = None


class AdminMessageItem(BaseModel):
    id: str
    role: str
    content: str
    created_at: Optional[datetime] = None


class AdminConversationItem(BaseModel):
    id: str
    title: Optional[str] = None
    topic: Optional[str] = None
    summary: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    messages: List[AdminMessageItem] = []


class AdminTopicItem(BaseModel):
    """话题池项"""
    id: str
    topic: str
    greeting: str
    age_start: Optional[int] = None
    age_end: Optional[int] = None
    created_at: Optional[datetime] = None


class AdminUserStats(BaseModel):
    """用户使用统计"""
    # 累计数据
    total_conversations: int = 0  # 总对话数
    total_memoirs: int = 0  # 总回忆录数
    total_messages: int = 0  # 总消息数
    total_duration_mins: Optional[float] = None  # 总对话时长（分钟）
    total_memoir_chars: int = 0  # 回忆录总字数
    # 平均数据
    avg_conversation_duration_mins: Optional[float] = None  # 平均对话时长（分钟）
    avg_messages_per_conversation: Optional[float] = None  # 平均每次对话消息数
    conversation_to_memoir_rate: Optional[float] = None  # 对话转化为回忆录的比率
    avg_memoir_length: Optional[int] = None  # 回忆录平均字数
    first_memoir_days: Optional[int] = None  # 首篇回忆录耗时（天）
    life_stages_coverage: dict = {}  # 回忆录覆盖的人生阶段 {阶段: 数量}


class AdminUserDetail(BaseModel):
    id: str
    phone: Optional[str] = None
    nickname: Optional[str] = None
    gender: Optional[str] = None
    preferred_name: Optional[str] = None  # 称呼（用户希望被怎么叫）
    birth_year: Optional[int] = None
    hometown: Optional[str] = None
    main_city: Optional[str] = None
    profile_completed: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    era_memories: Optional[str] = None  # 时代记忆
    memoirs: List[AdminMemoirDetailItem] = []
    conversations: List[AdminConversationItem] = []
    topic_pool: List[AdminTopicItem] = []  # 话题池
    stats: Optional[AdminUserStats] = None  # 使用统计


@admin_router.get("/user/{user_id}/detail", response_model=AdminUserDetail)
def admin_get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员获取用户详情，包括回忆录、对话记录、话题池和使用统计"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 获取用户的回忆录列表
    memoirs = db.query(Memoir).filter(Memoir.user_id == user_id).order_by(Memoir.order_index.asc()).all()
    memoir_items = []
    for m in memoirs:
        item = AdminMemoirDetailItem(
            id=m.id,
            title=m.title,
            content=m.content,
            status=m.status or "completed",
            year_start=m.year_start,
            year_end=m.year_end,
            time_period=m.time_period,
            conversation_id=m.conversation_id,
            conversation_start=None,
            conversation_end=None,
            created_at=m.created_at,
        )
        # 获取关联对话的时间范围
        if m.conversation and m.conversation.messages:
            messages = m.conversation.messages
            if messages:
                first_msg = messages[0]
                if first_msg.created_at:
                    item.conversation_start = first_msg.created_at.strftime("%Y-%m-%d %H:%M")
                last_msg = messages[-1]
                if last_msg.created_at:
                    item.conversation_end = last_msg.created_at.strftime("%Y-%m-%d %H:%M")
        memoir_items.append(item)

    # 获取用户的对话列表及消息
    conversations = db.query(Conversation).filter(Conversation.user_id == user_id).order_by(Conversation.created_at.desc()).all()
    conversation_items = []
    for c in conversations:
        conv_item = AdminConversationItem(
            id=c.id,
            title=c.title,
            topic=c.topic,
            summary=c.summary,
            status=c.status,
            created_at=c.created_at,
            messages=[
                AdminMessageItem(
                    id=msg.id,
                    role=msg.role,
                    content=msg.content,
                    created_at=msg.created_at,
                )
                for msg in (c.messages or [])
            ],
        )
        conversation_items.append(conv_item)

    # 获取话题池
    topic_candidates = db.query(TopicCandidate).filter(TopicCandidate.user_id == user_id).all()
    topic_pool = [
        AdminTopicItem(
            id=t.id,
            topic=t.topic,
            greeting=t.greeting,
            age_start=t.age_start,
            age_end=t.age_end,
            created_at=t.created_at,
        )
        for t in topic_candidates
    ]

    # 计算使用统计
    stats = _calculate_user_stats(user, memoirs, conversations)

    return AdminUserDetail(
        id=user.id,
        phone=user.phone,
        nickname=user.nickname,
        gender=user.gender,
        preferred_name=user.preferred_name,
        birth_year=user.birth_year,
        hometown=user.hometown,
        main_city=user.main_city,
        profile_completed=user.profile_completed or False,
        is_active=user.is_active if user.is_active is not None else True,
        created_at=user.created_at,
        era_memories=user.era_memories,
        memoirs=memoir_items,
        conversations=conversation_items,
        topic_pool=topic_pool,
        stats=stats,
    )


def _calculate_user_stats(user: User, memoirs: list, conversations: list) -> AdminUserStats:
    """计算用户使用统计"""
    stats = AdminUserStats()

    # 累计数据
    stats.total_conversations = len(conversations)
    stats.total_memoirs = len([m for m in memoirs if m.status == 'completed'])

    # 对话相关统计
    if conversations:
        # 总消息数和平均消息数
        total_messages = sum(len(c.messages or []) for c in conversations)
        stats.total_messages = total_messages
        stats.avg_messages_per_conversation = round(total_messages / len(conversations), 1)

        # 对话时长统计
        durations = []
        for c in conversations:
            if c.messages and len(c.messages) >= 2:
                first_msg = c.messages[0]
                last_msg = c.messages[-1]
                if first_msg.created_at and last_msg.created_at:
                    duration = (last_msg.created_at - first_msg.created_at).total_seconds() / 60
                    if duration > 0:
                        durations.append(duration)
        if durations:
            stats.total_duration_mins = round(sum(durations), 1)
            stats.avg_conversation_duration_mins = round(sum(durations) / len(durations), 1)

    # 回忆录相关统计
    completed_memoirs = [m for m in memoirs if m.status == 'completed']
    if completed_memoirs:
        # 回忆录总字数和平均字数
        total_length = sum(len(m.content or '') for m in completed_memoirs)
        stats.total_memoir_chars = total_length
        stats.avg_memoir_length = round(total_length / len(completed_memoirs))

        # 人生阶段覆盖
        stages = {}
        for m in completed_memoirs:
            if m.time_period:
                stages[m.time_period] = stages.get(m.time_period, 0) + 1
            elif m.year_start:
                # 根据年龄推断阶段
                if user.birth_year:
                    age = m.year_start - user.birth_year
                    if age < 12:
                        stage = '童年'
                    elif age < 18:
                        stage = '少年'
                    elif age < 30:
                        stage = '青年'
                    elif age < 50:
                        stage = '中年'
                    else:
                        stage = '晚年'
                    stages[stage] = stages.get(stage, 0) + 1
        stats.life_stages_coverage = stages

    # 对话转化率
    if conversations:
        memoir_conv_ids = {m.conversation_id for m in memoirs if m.conversation_id}
        converted = len([c for c in conversations if c.id in memoir_conv_ids])
        stats.conversation_to_memoir_rate = round(converted / len(conversations), 2)

    # 首篇回忆录耗时
    if completed_memoirs and user.created_at:
        first_memoir = min(completed_memoirs, key=lambda m: m.created_at or datetime.max)
        if first_memoir.created_at:
            days = (first_memoir.created_at - user.created_at).days
            stats.first_memoir_days = max(0, days)

    return stats


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


# ========== 管理员：数据监控 ==========


class OverviewStats(BaseModel):
    total_users: int
    profile_completed_users: int
    profile_completion_rate: float
    total_conversations: int
    total_memoirs: int


class ActivityStats(BaseModel):
    today_active_users: int
    week_active_users: int
    month_active_users: int
    today_new_conversations: int
    today_new_memoirs: int


class RetentionStats(BaseModel):
    day1: Optional[float] = None
    day7: Optional[float] = None
    day30: Optional[float] = None


class DistributionItem(BaseModel):
    label: str
    count: int


class DistributionStats(BaseModel):
    conversations_per_user: List[DistributionItem]
    memoirs_per_user: List[DistributionItem]
    messages_per_conversation: List[DistributionItem]
    birth_decade: List[DistributionItem]
    hometown_province: List[DistributionItem]


class MonitoringData(BaseModel):
    overview: OverviewStats
    activity: ActivityStats
    retention: RetentionStats
    distributions: DistributionStats


class RetentionMatrixRow(BaseModel):
    date: str
    new_users: int
    day1: Optional[float] = None
    day3: Optional[float] = None
    day7: Optional[float] = None
    day14: Optional[float] = None
    day30: Optional[float] = None


@admin_router.get("/monitoring", response_model=MonitoringData)
def admin_get_monitoring_data(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员获取数据监控统计"""
    from datetime import timedelta
    from sqlalchemy import func, case, and_, distinct

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today_start - timedelta(days=7)
    month_ago = today_start - timedelta(days=30)

    # ===== 总体概览 =====
    total_users = db.query(func.count(User.id)).scalar() or 0
    profile_completed_users = db.query(func.count(User.id)).filter(User.profile_completed == True).scalar() or 0
    total_conversations = db.query(func.count(Conversation.id)).scalar() or 0
    total_memoirs = db.query(func.count(Memoir.id)).scalar() or 0

    overview = OverviewStats(
        total_users=total_users,
        profile_completed_users=profile_completed_users,
        profile_completion_rate=round(profile_completed_users / total_users, 2) if total_users > 0 else 0,
        total_conversations=total_conversations,
        total_memoirs=total_memoirs,
    )

    # ===== 活跃度 =====
    # 活跃用户：有对话消息的用户
    today_active = db.query(func.count(distinct(Conversation.user_id))).filter(
        Conversation.created_at >= today_start
    ).scalar() or 0

    week_active = db.query(func.count(distinct(Conversation.user_id))).filter(
        Conversation.created_at >= week_ago
    ).scalar() or 0

    month_active = db.query(func.count(distinct(Conversation.user_id))).filter(
        Conversation.created_at >= month_ago
    ).scalar() or 0

    today_new_conversations = db.query(func.count(Conversation.id)).filter(
        Conversation.created_at >= today_start
    ).scalar() or 0

    today_new_memoirs = db.query(func.count(Memoir.id)).filter(
        Memoir.created_at >= today_start
    ).scalar() or 0

    activity = ActivityStats(
        today_active_users=today_active,
        week_active_users=week_active,
        month_active_users=month_active,
        today_new_conversations=today_new_conversations,
        today_new_memoirs=today_new_memoirs,
    )

    # ===== 留存率 =====
    def calc_retention(days: int) -> Optional[float]:
        """计算 N 日留存率"""
        cutoff_date = today_start - timedelta(days=days)
        # 在 cutoff_date 之前注册的用户
        eligible_users = db.query(User.id).filter(User.created_at < cutoff_date).subquery()
        eligible_count = db.query(func.count()).select_from(eligible_users).scalar() or 0
        if eligible_count == 0:
            return None
        # 这些用户中，在注册 N 天后仍有活动的用户
        retained_count = db.query(func.count(distinct(Conversation.user_id))).filter(
            Conversation.user_id.in_(db.query(eligible_users)),
            Conversation.created_at >= cutoff_date
        ).scalar() or 0
        return round(retained_count / eligible_count, 2)

    retention = RetentionStats(
        day1=calc_retention(1),
        day7=calc_retention(7),
        day30=calc_retention(30),
    )

    # ===== 分布统计 =====

    # 用户对话数分布
    conv_counts = db.query(
        Conversation.user_id,
        func.count(Conversation.id).label('cnt')
    ).group_by(Conversation.user_id).subquery()

    conv_dist_raw = db.query(
        case(
            (conv_counts.c.cnt == 0, '0'),
            (conv_counts.c.cnt <= 2, '1-2'),
            (conv_counts.c.cnt <= 5, '3-5'),
            else_='6+'
        ).label('range'),
        func.count().label('count')
    ).select_from(conv_counts).group_by('range').all()

    # 包含没有对话的用户
    users_with_conv = db.query(func.count(distinct(Conversation.user_id))).scalar() or 0
    users_without_conv = total_users - users_with_conv

    conv_dist = {r.range: r.count for r in conv_dist_raw}
    conv_dist['0'] = conv_dist.get('0', 0) + users_without_conv
    conversations_per_user = [
        DistributionItem(label='0', count=conv_dist.get('0', 0)),
        DistributionItem(label='1-2', count=conv_dist.get('1-2', 0)),
        DistributionItem(label='3-5', count=conv_dist.get('3-5', 0)),
        DistributionItem(label='6+', count=conv_dist.get('6+', 0)),
    ]

    # 用户回忆录数分布
    memoir_counts = db.query(
        Memoir.user_id,
        func.count(Memoir.id).label('cnt')
    ).group_by(Memoir.user_id).subquery()

    memoir_dist_raw = db.query(
        case(
            (memoir_counts.c.cnt == 0, '0'),
            (memoir_counts.c.cnt <= 2, '1-2'),
            (memoir_counts.c.cnt <= 5, '3-5'),
            else_='6+'
        ).label('range'),
        func.count().label('count')
    ).select_from(memoir_counts).group_by('range').all()

    users_with_memoir = db.query(func.count(distinct(Memoir.user_id))).scalar() or 0
    users_without_memoir = total_users - users_with_memoir

    memoir_dist = {r.range: r.count for r in memoir_dist_raw}
    memoir_dist['0'] = memoir_dist.get('0', 0) + users_without_memoir
    memoirs_per_user = [
        DistributionItem(label='0', count=memoir_dist.get('0', 0)),
        DistributionItem(label='1-2', count=memoir_dist.get('1-2', 0)),
        DistributionItem(label='3-5', count=memoir_dist.get('3-5', 0)),
        DistributionItem(label='6+', count=memoir_dist.get('6+', 0)),
    ]

    # 每次对话消息数分布
    msg_counts = db.query(
        Message.conversation_id,
        func.count(Message.id).label('cnt')
    ).group_by(Message.conversation_id).subquery()

    msg_dist_raw = db.query(
        case(
            (msg_counts.c.cnt <= 5, '1-5'),
            (msg_counts.c.cnt <= 10, '6-10'),
            (msg_counts.c.cnt <= 20, '11-20'),
            else_='20+'
        ).label('range'),
        func.count().label('count')
    ).select_from(msg_counts).group_by('range').all()

    msg_dist = {r.range: r.count for r in msg_dist_raw}
    messages_per_conversation = [
        DistributionItem(label='1-5', count=msg_dist.get('1-5', 0)),
        DistributionItem(label='6-10', count=msg_dist.get('6-10', 0)),
        DistributionItem(label='11-20', count=msg_dist.get('11-20', 0)),
        DistributionItem(label='20+', count=msg_dist.get('20+', 0)),
    ]

    # 出生年代分布
    decade_dist_raw = db.query(
        case(
            (User.birth_year < 1950, '40前'),
            (User.birth_year < 1960, '50后'),
            (User.birth_year < 1970, '60后'),
            (User.birth_year < 1980, '70后'),
            (User.birth_year < 1990, '80后'),
            else_='90后'
        ).label('decade'),
        func.count().label('count')
    ).filter(User.birth_year.isnot(None)).group_by('decade').all()

    birth_decade = [DistributionItem(label=r.decade, count=r.count) for r in decade_dist_raw]
    # 添加未填写的用户
    users_without_birth = db.query(func.count(User.id)).filter(User.birth_year.is_(None)).scalar() or 0
    if users_without_birth > 0:
        birth_decade.append(DistributionItem(label='未填写', count=users_without_birth))

    # 家乡省份分布（提取省份）
    # 简单处理：取 hometown 的前2-3个字作为省份
    hometown_raw = db.query(User.hometown).filter(User.hometown.isnot(None), User.hometown != '').all()
    province_counts = {}
    for (hometown,) in hometown_raw:
        if not hometown:
            continue
        # 提取省份（简单处理：取前2-3个字）
        province = hometown[:2] if len(hometown) >= 2 else hometown
        # 处理特殊情况
        if province in ['内蒙', '黑龙']:
            province = hometown[:3] if len(hometown) >= 3 else province
        province_counts[province] = province_counts.get(province, 0) + 1

    # 排序取 Top 10
    sorted_provinces = sorted(province_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    hometown_province = [DistributionItem(label=p, count=c) for p, c in sorted_provinces]

    users_without_hometown = db.query(func.count(User.id)).filter(
        (User.hometown.is_(None)) | (User.hometown == '')
    ).scalar() or 0
    if users_without_hometown > 0:
        hometown_province.append(DistributionItem(label='未填写', count=users_without_hometown))

    distributions = DistributionStats(
        conversations_per_user=conversations_per_user,
        memoirs_per_user=memoirs_per_user,
        messages_per_conversation=messages_per_conversation,
        birth_decade=birth_decade,
        hometown_province=hometown_province,
    )

    return MonitoringData(
        overview=overview,
        activity=activity,
        retention=retention,
        distributions=distributions,
    )


@admin_router.get("/monitoring/retention-matrix", response_model=List[RetentionMatrixRow])
def admin_get_retention_matrix(
    days: int = 30,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员获取留存矩阵数据"""
    from datetime import timedelta
    from sqlalchemy import func, distinct

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    result = []

    # 按注册日期分组，计算每天的留存
    for i in range(days, 0, -1):
        target_date = today_start - timedelta(days=i)
        next_date = target_date + timedelta(days=1)

        # 当天注册的用户
        new_users_query = db.query(User.id).filter(
            User.created_at >= target_date,
            User.created_at < next_date
        )
        new_user_ids = [u.id for u in new_users_query.all()]
        new_users_count = len(new_user_ids)

        if new_users_count == 0:
            continue

        row = RetentionMatrixRow(
            date=target_date.strftime('%m-%d'),
            new_users=new_users_count,
        )

        # 计算各天留存
        for retention_day, attr_name in [(1, 'day1'), (3, 'day3'), (7, 'day7'), (14, 'day14'), (30, 'day30')]:
            retention_date = target_date + timedelta(days=retention_day)
            if retention_date > today_start:
                # 还没到这一天
                continue

            # 在 retention_date 当天或之后有活动的用户数
            retained = db.query(func.count(distinct(Conversation.user_id))).filter(
                Conversation.user_id.in_(new_user_ids),
                Conversation.created_at >= retention_date
            ).scalar() or 0

            setattr(row, attr_name, round(retained / new_users_count, 2) if new_users_count > 0 else 0)

        result.append(row)

    return result


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


# ========== 管理员：激励语管理 ==========

class WelcomeMessageItem(BaseModel):
    id: str
    content: str
    show_greeting: bool = True
    is_active: bool = True
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class WelcomeMessageCreateRequest(BaseModel):
    content: str
    show_greeting: bool = True
    is_active: bool = True
    sort_order: int = 0


class WelcomeMessageUpdateRequest(BaseModel):
    content: Optional[str] = None
    show_greeting: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


@admin_router.get("/welcome-messages", response_model=List[WelcomeMessageItem])
def admin_list_welcome_messages(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员获取所有激励语（含禁用的）"""
    messages = db.query(WelcomeMessage).order_by(WelcomeMessage.sort_order.asc(), WelcomeMessage.created_at.asc()).all()
    return [
        WelcomeMessageItem(
            id=m.id,
            content=m.content,
            show_greeting=m.show_greeting,
            is_active=m.is_active,
            sort_order=m.sort_order,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in messages
    ]


@admin_router.post("/welcome-messages", response_model=WelcomeMessageItem)
def admin_create_welcome_message(
    req: WelcomeMessageCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员新增激励语"""
    msg = WelcomeMessage(
        content=req.content,
        show_greeting=req.show_greeting,
        is_active=req.is_active,
        sort_order=req.sort_order,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    _log_action(db, "create_welcome_message", None, None,
                f"新增激励语：{msg.content[:50]}")
    return WelcomeMessageItem(
        id=msg.id,
        content=msg.content,
        show_greeting=msg.show_greeting,
        is_active=msg.is_active,
        sort_order=msg.sort_order,
        created_at=msg.created_at,
        updated_at=msg.updated_at,
    )


@admin_router.put("/welcome-messages/{message_id}", response_model=WelcomeMessageItem)
def admin_update_welcome_message(
    message_id: str,
    req: WelcomeMessageUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员编辑激励语"""
    msg = db.query(WelcomeMessage).filter(WelcomeMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="激励语不存在")

    if req.content is not None:
        msg.content = req.content
    if req.show_greeting is not None:
        msg.show_greeting = req.show_greeting
    if req.is_active is not None:
        msg.is_active = req.is_active
    if req.sort_order is not None:
        msg.sort_order = req.sort_order

    db.commit()
    db.refresh(msg)
    _log_action(db, "update_welcome_message", None, None,
                f"编辑激励语：{msg.content[:50]}")
    return WelcomeMessageItem(
        id=msg.id,
        content=msg.content,
        show_greeting=msg.show_greeting,
        is_active=msg.is_active,
        sort_order=msg.sort_order,
        created_at=msg.created_at,
        updated_at=msg.updated_at,
    )


@admin_router.delete("/welcome-messages/{message_id}")
def admin_delete_welcome_message(
    message_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员删除激励语"""
    msg = db.query(WelcomeMessage).filter(WelcomeMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="激励语不存在")

    content_preview = msg.content[:50] if msg.content else ""
    db.delete(msg)
    db.commit()
    _log_action(db, "delete_welcome_message", None, None,
                f"删除激励语：{content_preview}")
    return {"success": True}


# ========== 管理员：预设话题管理 ==========

class PresetTopicItem(BaseModel):
    id: str
    topic: str
    greeting: str
    chat_context: Optional[str] = None
    age_start: Optional[int] = None
    age_end: Optional[int] = None
    is_active: bool = True
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PresetTopicCreateRequest(BaseModel):
    topic: str
    greeting: str
    chat_context: Optional[str] = None
    age_start: Optional[int] = None
    age_end: Optional[int] = None
    is_active: bool = True
    sort_order: int = 0


class PresetTopicUpdateRequest(BaseModel):
    topic: Optional[str] = None
    greeting: Optional[str] = None
    chat_context: Optional[str] = None
    age_start: Optional[int] = None
    age_end: Optional[int] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


@admin_router.get("/preset-topics", response_model=List[PresetTopicItem])
def admin_list_preset_topics(
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员获取所有预设话题（含禁用的）"""
    topics = db.query(PresetTopic).order_by(PresetTopic.sort_order.asc(), PresetTopic.created_at.asc()).all()
    return [
        PresetTopicItem(
            id=t.id,
            topic=t.topic,
            greeting=t.greeting,
            chat_context=t.chat_context,
            age_start=t.age_start,
            age_end=t.age_end,
            is_active=t.is_active,
            sort_order=t.sort_order,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in topics
    ]


@admin_router.post("/preset-topics", response_model=PresetTopicItem)
def admin_create_preset_topic(
    req: PresetTopicCreateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员新增预设话题"""
    topic = PresetTopic(
        topic=req.topic,
        greeting=req.greeting,
        chat_context=req.chat_context,
        age_start=req.age_start,
        age_end=req.age_end,
        is_active=req.is_active,
        sort_order=req.sort_order,
    )
    db.add(topic)
    db.commit()
    db.refresh(topic)
    _log_action(db, "create_preset_topic", None, None,
                f"新增预设话题：{topic.topic}")
    return PresetTopicItem(
        id=topic.id,
        topic=topic.topic,
        greeting=topic.greeting,
        chat_context=topic.chat_context,
        age_start=topic.age_start,
        age_end=topic.age_end,
        is_active=topic.is_active,
        sort_order=topic.sort_order,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
    )


@admin_router.put("/preset-topics/{topic_id}", response_model=PresetTopicItem)
def admin_update_preset_topic(
    topic_id: str,
    req: PresetTopicUpdateRequest,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员编辑预设话题"""
    topic = db.query(PresetTopic).filter(PresetTopic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="预设话题不存在")

    if req.topic is not None:
        topic.topic = req.topic
    if req.greeting is not None:
        topic.greeting = req.greeting
    if req.chat_context is not None:
        topic.chat_context = req.chat_context
    if req.age_start is not None:
        topic.age_start = req.age_start
    if req.age_end is not None:
        topic.age_end = req.age_end
    if req.is_active is not None:
        topic.is_active = req.is_active
    if req.sort_order is not None:
        topic.sort_order = req.sort_order

    db.commit()
    db.refresh(topic)
    _log_action(db, "update_preset_topic", None, None,
                f"编辑预设话题：{topic.topic}")
    return PresetTopicItem(
        id=topic.id,
        topic=topic.topic,
        greeting=topic.greeting,
        chat_context=topic.chat_context,
        age_start=topic.age_start,
        age_end=topic.age_end,
        is_active=topic.is_active,
        sort_order=topic.sort_order,
        created_at=topic.created_at,
        updated_at=topic.updated_at,
    )


@admin_router.delete("/preset-topics/{topic_id}")
def admin_delete_preset_topic(
    topic_id: str,
    db: Session = Depends(get_db),
    _: None = Depends(verify_admin_key),
):
    """管理员删除预设话题"""
    topic = db.query(PresetTopic).filter(PresetTopic.id == topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="预设话题不存在")

    topic_name = topic.topic
    db.delete(topic)
    db.commit()
    _log_action(db, "delete_preset_topic", None, None,
                f"删除预设话题：{topic_name}")
    return {"success": True}


# ========== 管理员：LLM 健康监控 ==========


@admin_router.get("/llm-models")
def admin_list_llm_models(
    _: None = Depends(verify_admin_key),
):
    """返回所有已配置的 LLM 模型列表"""
    from app.config import settings
    from app.services.llm_client import _MODULE_OVERRIDE, _resolve_provider

    providers_info = {}

    # DashScope（始终存在）
    providers_info["dashscope"] = {
        "main": settings.dashscope_model,
        "fast": settings.dashscope_model_fast,
        "api_key_set": bool(settings.dashscope_api_key),
    }

    # Gemini（有 api_key 才显示）
    if settings.gemini_api_key:
        providers_info["gemini"] = {
            "main": settings.gemini_model,
            "fast": settings.gemini_model_fast,
            "api_key_set": True,
        }

    # 构建模块路由映射：哪些模块路由到了哪个 provider
    module_routing = {}  # provider -> list of module names
    for module_name in _MODULE_OVERRIDE:
        provider = _resolve_provider(module_name)
        module_routing.setdefault(provider, []).append(module_name)

    # 构建结果
    models = []
    for provider_name, info in providers_info.items():
        routed_modules = module_routing.get(provider_name, [])
        for tier in ["main", "fast"]:
            models.append({
                "provider": provider_name,
                "model": info[tier],
                "tier": tier,
                "modules": routed_modules,
                "api_key_set": info["api_key_set"],
            })

    return {
        "models": models,
        "default_provider": settings.llm_provider_default,
        "module_overrides": {
            module: _resolve_provider(module) for module in _MODULE_OVERRIDE
        },
    }


class HealthCheckRequest(BaseModel):
    provider: str
    model: str


@admin_router.post("/llm-health-check")
async def admin_llm_health_check(
    req: HealthCheckRequest,
    _: None = Depends(verify_admin_key),
):
    """测试单个 LLM 模型的连通性"""
    from app.services.llm_client import _get_provider_instance

    logger.info("[HealthCheck] 开始测试: provider=%s, model=%s", req.provider, req.model)
    start = time.time()
    try:
        provider_instance = _get_provider_instance(req.provider)
        resp = await provider_instance.achat(
            req.model,
            [{"role": "user", "content": "你好，请回复OK。"}],
            max_tokens=20,
            temperature=0,
        )
        latency_ms = round((time.time() - start) * 1000)
        logger.info(
            "[HealthCheck] 测试成功: provider=%s, model=%s, latency=%dms, response=%s",
            req.provider, req.model, latency_ms, resp.content,
        )
        return {
            "success": True,
            "latency_ms": latency_ms,
            "response_text": resp.content or "",
            "error": None,
        }
    except Exception as e:
        latency_ms = round((time.time() - start) * 1000)
        logger.error(
            "[HealthCheck] 测试失败: provider=%s, model=%s, latency=%dms, "
            "error_type=%s, error=%s",
            req.provider, req.model, latency_ms,
            type(e).__name__, e,
            exc_info=True,
        )
        return {
            "success": False,
            "latency_ms": latency_ms,
            "response_text": None,
            "error": str(e),
        }
