from sqlalchemy.orm import Session
from typing import List, Optional, Generator
from app.models import Conversation, Message
from app.services.llm_service import llm_service
from app.prompts import SYSTEM_PROMPT, FIRST_MESSAGE


class ChatService:
    def start_conversation(self, db: Session, user_id: str) -> tuple[Conversation, str]:
        """开始新对话，返回对话对象和AI的第一条消息"""
        conversation = Conversation(user_id=user_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        # 保存AI的第一条消息
        first_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=FIRST_MESSAGE
        )
        db.add(first_msg)
        db.commit()

        return conversation, FIRST_MESSAGE

    def chat(self, db: Session, conversation_id: str, user_message: str) -> str:
        """处理用户消息，返回AI回复"""
        # 保存用户消息
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        db.commit()

        # 获取历史消息
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        # 构建对话历史
        history = [{"role": msg.role, "content": msg.content} for msg in messages]

        # 调用大模型
        ai_response = llm_service.chat(history, SYSTEM_PROMPT)

        # 保存AI回复
        ai_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=ai_response
        )
        db.add(ai_msg)
        db.commit()

        return ai_response

    def chat_stream(self, db: Session, conversation_id: str, user_message: str) -> Generator[str, None, str]:
        """流式处理用户消息，逐步返回AI回复"""
        # 保存用户消息
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        db.commit()

        # 获取历史消息
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        # 构建对话历史
        history = [{"role": msg.role, "content": msg.content} for msg in messages]

        # 流式调用大模型
        full_response = ""
        for chunk in llm_service.chat_stream(history, SYSTEM_PROMPT):
            full_response += chunk
            yield chunk

        # 保存完整的AI回复
        ai_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=full_response
        )
        db.add(ai_msg)
        db.commit()

        return full_response

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
