from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON
from datetime import datetime
import uuid

from app.database import Base


class Memoir(Base):
    __tablename__ = "memoirs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    source_conversations = Column(JSON, default=list)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
