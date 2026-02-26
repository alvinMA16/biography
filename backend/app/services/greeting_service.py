"""
开场白服务
- 为新用户生成初始开场白
- 对话结束后刷新开场白池
- 随机获取开场白
"""
import random
from typing import List, Optional
from sqlalchemy.orm import Session
from openai import OpenAI

from app.config import settings
from app.models import User, GreetingCandidate, Conversation, Message


class GreetingService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = settings.dashscope_model

    def get_random_greeting(self, db: Session, user_id: str) -> Optional[str]:
        """获取随机开场白"""
        candidates = db.query(GreetingCandidate).filter(
            GreetingCandidate.user_id == user_id
        ).all()

        if not candidates:
            return None

        return random.choice(candidates).content

    def generate_initial_greetings(self, db: Session, user: User) -> List[str]:
        """为新用户生成初始开场白（完成信息收集后调用）"""
        from app.prompts import greeting

        print(f"[Greeting] 为用户 {user.id} 生成初始开场白")

        # 构建用户画像
        profile = self._build_user_profile(user)
        prompt = greeting.build_initial(profile)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=1000
            )

            content = response.choices[0].message.content.strip()
            greetings = [line.strip() for line in content.split("\n") if line.strip()]

            # 保存到数据库
            self._save_greetings(db, user.id, greetings, "initial")

            print(f"[Greeting] 生成了 {len(greetings)} 条初始开场白")
            return greetings

        except Exception as e:
            print(f"[Greeting] 生成初始开场白失败: {e}")
            # 返回默认开场白
            default = greeting.DEFAULT_GREETINGS
            self._save_greetings(db, user.id, default, "default")
            return default

    def refresh_greetings(self, db: Session, user_id: str) -> List[str]:
        """对话结束后刷新开场白池"""
        from app.prompts import greeting

        print(f"[Greeting] 刷新用户 {user_id} 的开场白池")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        # 获取用户画像
        profile = self._build_user_profile(user)

        # 获取对话历史摘要
        history = self._get_conversation_history(db, user_id)

        prompt = greeting.build_refresh(profile, history)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.9,
                max_tokens=1000
            )

            content = response.choices[0].message.content.strip()
            greetings = [line.strip() for line in content.split("\n") if line.strip()]

            # 清空旧的，保存新的
            db.query(GreetingCandidate).filter(
                GreetingCandidate.user_id == user_id
            ).delete()

            self._save_greetings(db, user_id, greetings, f"after_conversations:{history[:100] if history else 'none'}")

            print(f"[Greeting] 刷新完成，新增 {len(greetings)} 条开场白")
            return greetings

        except Exception as e:
            print(f"[Greeting] 刷新开场白失败: {e}")
            return []

    def _build_user_profile(self, user: User) -> str:
        """构建用户画像文本"""
        parts = []
        if user.nickname:
            parts.append(f"- 称呼: {user.nickname}")
        if user.birth_year:
            parts.append(f"- 出生年份: {user.birth_year}年")
        if user.hometown:
            parts.append(f"- 家乡: {user.hometown}")

        return "\n".join(parts) if parts else "（暂无用户信息）"

    def _get_conversation_history(self, db: Session, user_id: str) -> str:
        """获取用户的对话历史摘要"""
        conversations = db.query(Conversation).filter(
            Conversation.user_id == user_id,
            Conversation.status == "completed"
        ).order_by(Conversation.created_at.desc()).limit(10).all()

        if not conversations:
            return ""

        summaries = []
        for conv in conversations:
            if conv.summary:
                summaries.append(f"- {conv.summary}")
            elif conv.topic:
                summaries.append(f"- 主题: {conv.topic}")

        return "\n".join(summaries) if summaries else ""

    def _save_greetings(self, db: Session, user_id: str, greetings: List[str], context: str):
        """保存开场白到数据库"""
        for greeting in greetings:
            if greeting:
                candidate = GreetingCandidate(
                    user_id=user_id,
                    content=greeting,
                    context=context
                )
                db.add(candidate)
        db.commit()



greeting_service = GreetingService()
