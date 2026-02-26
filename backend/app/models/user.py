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
    main_city = Column(String(100), nullable=True)  # 生活时间最长的城市
    profile_completed = Column(Boolean, default=False)  # 是否完成基础信息收集
    era_memories = Column(Text, nullable=True)  # 时代记忆（LLM 生成）
    # 时代记忆状态: none(未收集基础信息) / pending(等待生成) / generating(生成中) / completed(已完成) / failed(失败)
    era_memories_status = Column(String(20), default='none')

    # 话题候选池
    topic_candidates = relationship("TopicCandidate", back_populates="user", cascade="all, delete-orphan")

    # 旧的开场白候选池（兼容）
    greeting_candidates = relationship("GreetingCandidate", back_populates="user", cascade="all, delete-orphan")


class TopicCandidate(Base):
    """预生成的话题候选（用户开始新对话时选择）"""
    __tablename__ = "topic_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    topic = Column(String(200), nullable=False)  # 话题描述（给用户看的选项）
    greeting = Column(Text, nullable=False)  # 对应的开场白
    chat_context = Column(Text, nullable=True)  # 对话时注入的背景上下文
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="topic_candidates")


class GreetingCandidate(Base):
    """预生成的开场白候选（旧版，保留兼容）"""
    __tablename__ = "greeting_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)  # 开场白内容
    topic = Column(String(50), nullable=True)  # 相关主题（可选）
    context = Column(Text, nullable=True)  # 生成时的上下文参考（便于调试）
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="greeting_candidates")
