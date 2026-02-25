from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


class Memoir(Base):
    __tablename__ = "memoirs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    conversation_id = Column(String(36), ForeignKey("conversations.id"), nullable=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=True)  # 生成中时可能为空
    status = Column(String(20), default="completed")  # generating, completed
    source_conversations = Column(JSON, default=list)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联对话，用于获取对话时间
    conversation = relationship("Conversation", foreign_keys=[conversation_id])
