from sqlalchemy.orm import Session
from typing import List, Optional, Generator
from app.models import Conversation, Message
from app.services.llm_service import llm_service


class ChatService:
    def start_conversation(self, db: Session, user_id: str) -> tuple[Conversation, str]:
        """开始新对话，返回对话对象（实时语音模式下第一条消息由WebSocket处理）"""
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        # 实时语音模式下，开场白由 WebSocket 处理，这里不保存第一条消息
        return conversation, ""

    def chat(self, db: Session, conversation_id: str, user_message: str) -> str:
        """处理用户消息（已弃用，仅保留兼容性）"""
        raise NotImplementedError("文本聊天模式已弃用，请使用实时语音对话")

    def chat_stream(self, db: Session, conversation_id: str, user_message: str) -> Generator[str, None, str]:
        """流式处理用户消息（已弃用，仅保留兼容性）"""
        raise NotImplementedError("文本聊天模式已弃用，请使用实时语音对话")

    def end_conversation(self, db: Session, conversation_id: str) -> Conversation:
        """结束对话，生成摘要"""
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conversation:
            return None

        # 获取所有消息
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        # 构建对话文本
        conversation_text = "\n".join([
            f"{'老人' if msg.role == 'user' else 'AI'}: {msg.content}"
            for msg in messages
        ])

        # 生成摘要
        summary = llm_service.generate_summary(conversation_text)

        # 更新对话状态
        conversation.status = "completed"
        conversation.summary = summary
        db.commit()
        db.refresh(conversation)

        return conversation

    def end_conversation_quick(self, db: Session, conversation_id: str) -> Conversation:
        """快速结束对话（不生成摘要）"""
        conversation = db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

        if not conversation:
            return None

        # 只更新状态，不生成摘要
        conversation.status = "completed"
        db.commit()
        db.refresh(conversation)

        return conversation

    def get_conversation(self, db: Session, conversation_id: str) -> Optional[Conversation]:
        """获取对话详情"""
        return db.query(Conversation).filter(
            Conversation.id == conversation_id
        ).first()

    def get_user_conversations(self, db: Session, user_id: str) -> List[Conversation]:
        """获取用户的所有对话"""
        return db.query(Conversation).filter(
            Conversation.user_id == user_id
        ).order_by(Conversation.created_at.desc()).all()


chat_service = ChatService()
