from sqlalchemy.orm import Session
from typing import List, Optional
from app.models import Memoir, Conversation, Message, User
from app.services.llm_service import llm_service
from app.services.memoir_agent import memoir_agent


class MemoirService:
    def _get_conversation_text(self, db: Session, conversation_id: str) -> str:
        """获取对话文本"""
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        return "\n".join([
            f"{'用户' if msg.role == 'user' else '记录师'}: {msg.content}"
            for msg in messages
        ])

    def create_generating(
        self,
        db: Session,
        user_id: str,
        conversation_id: str,
    ) -> Memoir:
        """创建一个"撰写中"状态的回忆录"""
        # 获取对话文本
        conversation_text = self._get_conversation_text(db, conversation_id)

        # 生成标题
        if conversation_text.strip():
            title = llm_service.generate_title(conversation_text)
        else:
            title = "新回忆"

        # 获取现有回忆录数量，用于排序
        count = db.query(Memoir).filter(Memoir.user_id == user_id).count()

        # 创建回忆录（撰写中状态）
        memoir = Memoir(
            user_id=user_id,
            conversation_id=conversation_id,
            title=title,
            content=None,
            status="generating",
            source_conversations=[conversation_id],
            order_index=count
        )
        db.add(memoir)
        db.commit()
        db.refresh(memoir)

        return memoir

    def complete_generation(
        self,
        db: Session,
        memoir_id: str,
        perspective: str = "第一人称"
    ) -> Memoir:
        """完成回忆录内容生成"""
        memoir = db.query(Memoir).filter(Memoir.id == memoir_id).first()
        if not memoir:
            return None

        # 获取对话文本
        conversation_text = self._get_conversation_text(db, memoir.conversation_id)

        # 使用 Agent 生成回忆录内容
        if conversation_text.strip():
            content = memoir_agent.generate(conversation_text, perspective)
        else:
            content = "（对话内容为空）"

        # 更新回忆录
        memoir.content = content
        memoir.status = "completed"
        db.commit()
        db.refresh(memoir)

        return memoir

    def generate_from_conversation(
        self,
        db: Session,
        user_id: str,
        conversation_id: str,
        title: str = None,
        perspective: str = "第一人称"
    ) -> Memoir:
        """从单个对话生成回忆录章节（同步方式）"""
        # 获取对话文本
        conversation_text = self._get_conversation_text(db, conversation_id)

        # 生成标题（如果没有提供）
        if not title:
            if conversation_text.strip():
                title = llm_service.generate_title(conversation_text)
            else:
                title = "新回忆"

        # 使用 Agent 生成回忆录内容
        if conversation_text.strip():
            content = memoir_agent.generate(conversation_text, perspective)
        else:
            content = "（对话内容为空）"

        # 获取用户出生年份，用于推断时间段
        user = db.query(User).filter(User.id == user_id).first()
        birth_year = user.birth_year if user else None

        # 推断时间段
        time_info = {"year_start": None, "year_end": None, "time_period": ""}
        if conversation_text.strip():
            time_info = llm_service.infer_time_period(conversation_text, birth_year)
            print(f"[Memoir] 推断时间段: {time_info}")

        # 获取现有回忆录数量，用于排序
        count = db.query(Memoir).filter(Memoir.user_id == user_id).count()

        # 创建回忆录
        memoir = Memoir(
            user_id=user_id,
            conversation_id=conversation_id,
            title=title,
            content=content,
            status="completed",
            source_conversations=[conversation_id],
            order_index=count,
            year_start=time_info.get("year_start"),
            year_end=time_info.get("year_end"),
            time_period=time_info.get("time_period")
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

    def regenerate(
        self,
        db: Session,
        memoir_id: str,
        perspective: str = "第一人称"
    ) -> Optional[Memoir]:
        """重新生成回忆录内容"""
        memoir = db.query(Memoir).filter(Memoir.id == memoir_id).first()
        if not memoir:
            return None

        # 需要有关联的对话才能重新生成
        if not memoir.conversation_id:
            return None

        # 获取对话文本
        conversation_text = self._get_conversation_text(db, memoir.conversation_id)

        if not conversation_text.strip():
            return None

        # 使用 Agent 重新生成内容
        content = memoir_agent.generate(conversation_text, perspective)

        # 更新回忆录
        memoir.content = content
        db.commit()
        db.refresh(memoir)

        return memoir


memoir_service = MemoirService()
