from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import Memoir, Conversation, Message
from app.services.llm_service import llm_service


class MemoirService:
    def generate_from_conversation(
        self,
        db: Session,
        user_id: str,
        conversation_id: str,
        title: str = None,
        perspective: str = "第一人称"
    ) -> Memoir:
        """从单个对话生成回忆录章节"""
        # 获取对话消息
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        # 构建对话文本
        conversation_text = "\n".join([
            f"{'老人' if msg.role == 'user' else '晚辈'}: {msg.content}"
            for msg in messages
        ])

        # 生成回忆录内容
        content = llm_service.generate_memoir(conversation_text, perspective)

        # 获取现有回忆录数量，用于排序
        count = db.query(Memoir).filter(Memoir.user_id == user_id).count()

        # 创建回忆录
        memoir = Memoir(
            user_id=user_id,
            title=title or f"回忆片段 {count + 1}",
            content=content,
            source_conversations=[conversation_id],
            order_index=count
        )
        db.add(memoir)
        db.commit()
        db.refresh(memoir)

        return memoir

    def get_user_memoirs(self, db: Session, user_id: str) -> List[Memoir]:
        """获取用户的所有回忆录章节"""
        return db.query(Memoir).filter(
            Memoir.user_id == user_id
        ).order_by(Memoir.order_index).all()

    def get_memoir(self, db: Session, memoir_id: str) -> Optional[Memoir]:
        """获取单个回忆录章节"""
        return db.query(Memoir).filter(Memoir.id == memoir_id).first()

    def update_memoir(
        self,
        db: Session,
        memoir_id: str,
        title: str = None,
        content: str = None
    ) -> Optional[Memoir]:
        """更新回忆录"""
        memoir = db.query(Memoir).filter(Memoir.id == memoir_id).first()
        if not memoir:
            return None

        if title:
            memoir.title = title
        if content:
            memoir.content = content

        db.commit()
        db.refresh(memoir)
        return memoir

    def delete_memoir(self, db: Session, memoir_id: str) -> bool:
        """删除回忆录"""
        memoir = db.query(Memoir).filter(Memoir.id == memoir_id).first()
        if not memoir:
            return False

        db.delete(memoir)
        db.commit()
        return True


memoir_service = MemoirService()
