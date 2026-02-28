from sqlalchemy import Column, String, DateTime, Text
from datetime import datetime
import uuid

from app.database import Base


class AuditLog(Base):
    """管理员操作日志"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(50), nullable=False)       # 操作类型: create_user, edit_user, reset_password
    target_user_id = Column(String(36), nullable=True)  # 操作对象用户 ID
    target_label = Column(String(100), nullable=True)   # 操作对象标签（手机号/昵称，方便展示）
    detail = Column(Text, nullable=True)                # 操作详情
    created_at = Column(DateTime, default=datetime.utcnow)
