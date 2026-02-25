from sqlalchemy import Column, String, DateTime, JSON, Integer, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nickname = Column(String(32), nullable=True)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 用户基础信息（通过对话收集）
    birth_year = Column(Integer, nullable=True)  # 出生年份
    hometown = Column(String(100), nullable=True)  # 家乡
    profile_completed = Column(Boolean, default=False)  # 是否完成基础信息收集

    # 开场白候选池
    greeting_candidates = relationship("GreetingCandidate", back_populates="user", cascade="all, delete-orphan")


class GreetingCandidate(Base):
    """预生成的开场白候选"""
    __tablename__ = "greeting_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)  # 开场白内容
    topic = Column(String(50), nullable=True)  # 相关主题（可选）
    context = Column(Text, nullable=True)  # 生成时的上下文参考（便于调试）
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="greeting_candidates")
