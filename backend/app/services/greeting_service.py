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
        print(f"[Greeting] 为用户 {user.id} 生成初始开场白")

        # 构建用户画像
        profile = self._build_user_profile(user)

        prompt = f"""你是一位回忆录记录师，正准备和一位用户开始第一次正式的回忆访谈。

## 用户信息
{profile}

## 任务
请生成 5 条不同的开场白，每条开场白应该：
1. 亲切自然，像晚辈和长辈聊天
2. 提出一个具体的、容易回答的问题
3. 涉及不同的人生阶段或主题（童年、求学、工作、家庭、爱好等）
4. 问题要具体，不要太宽泛

## 格式
每条开场白独占一行，不要编号，不要其他说明。
"""

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
            default = self._get_default_greetings()
            self._save_greetings(db, user.id, default, "default")
            return default

    def refresh_greetings(self, db: Session, user_id: str) -> List[str]:
        """对话结束后刷新开场白池"""
        print(f"[Greeting] 刷新用户 {user_id} 的开场白池")

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return []

        # 获取用户画像
        profile = self._build_user_profile(user)

        # 获取对话历史摘要
        history = self._get_conversation_history(db, user_id)

        prompt = f"""你是一位回忆录记录师，正准备和用户进行下一次回忆访谈。

## 用户信息
{profile}

## 已有的对话记录
{history if history else "（这是第一次对话）"}

## 任务
根据用户信息和已有的对话记录，生成 5 条下次访谈可以使用的开场白。

要求：
1. 避免重复询问已经聊过的内容
2. 可以深入挖掘之前提到但没有展开的话题
3. 也可以探索全新的人生阶段或主题
4. 问题要具体，容易回答
5. 语气亲切自然

## 格式
每条开场白独占一行，不要编号，不要其他说明。
"""

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

    def _get_default_greetings(self) -> List[str]:
        """默认开场白"""
        return [
            "您好！今天想听您讲讲您的故事。您最近有没有想起什么往事？",
            "您好！很高兴能陪您聊聊天。您小时候住在哪里？那时候的生活是什么样的？",
            "您好！我特别想听听您的故事。您年轻的时候是做什么工作的？",
            "您好！今天咱们聊聊您的经历吧。您还记得上学时候的事情吗？",
            "您好！想请您讲讲您印象最深的一件事，可以吗？",
        ]


greeting_service = GreetingService()
