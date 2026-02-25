"""
用户信息服务
- 从对话中提取用户基础信息
- 更新用户资料
- 触发初始开场白生成
"""
import json
from typing import Optional, Dict
from sqlalchemy.orm import Session
from openai import OpenAI

from app.config import settings
from app.models import User, Conversation, Message
from app.services.greeting_service import greeting_service


class ProfileService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = settings.dashscope_model

    def extract_and_update_profile(self, db: Session, conversation_id: str, user_id: str) -> bool:
        """
        从对话中提取用户信息并更新数据库

        Returns:
            是否成功提取并更新
        """
        print(f"[Profile] 开始从对话 {conversation_id} 提取用户信息")

        # 获取对话消息
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        if not messages:
            print(f"[Profile] 对话消息为空")
            return False

        # 构建对话文本
        conversation_text = "\n".join([
            f"{'用户' if msg.role == 'user' else '记录师'}: {msg.content}"
            for msg in messages
        ])

        # 使用 LLM 提取信息
        prompt = f"""请从以下对话中提取用户的基本信息。

## 对话内容
{conversation_text}

## 需要提取的信息
1. nickname - 用户希望被称呼的名字（如：张爷爷、李阿姨、老王等）
2. birth_year - 出生年份（4位数字，如：1950）
3. hometown - 家乡或出生地（如：北京、山东济南等）

## 输出格式（JSON）
{{
    "nickname": "提取到的称呼，如果没有提到则为null",
    "birth_year": 提取到的年份数字，如果没有提到则为null,
    "hometown": "提取到的地点，如果没有提到则为null",
    "has_enough_info": true或false（是否收集到了至少称呼信息）
}}

只输出 JSON，不要其他内容。如果用户说了年龄，请根据当前年份（2024年）计算出出生年份。
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )

            content = response.choices[0].message.content.strip()

            # 处理可能的 markdown 代码块
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            print(f"[Profile] 提取结果: {result}")

            # 更新用户信息
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                print(f"[Profile] 用户不存在: {user_id}")
                return False

            updated = False

            if result.get("nickname"):
                user.nickname = result["nickname"]
                updated = True

            if result.get("birth_year"):
                user.birth_year = int(result["birth_year"])
                updated = True

            if result.get("hometown"):
                user.hometown = result["hometown"]
                updated = True

            # 如果收集到了足够信息，标记为完成
            if result.get("has_enough_info") or user.nickname:
                user.profile_completed = True
                print(f"[Profile] 用户信息收集完成: nickname={user.nickname}, birth_year={user.birth_year}, hometown={user.hometown}")

                db.commit()

                # 生成初始开场白
                greeting_service.generate_initial_greetings(db, user)

                return True
            else:
                print(f"[Profile] 信息不足，未标记为完成")
                if updated:
                    db.commit()
                return False

        except Exception as e:
            print(f"[Profile] 提取用户信息失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def is_profile_completed(self, db: Session, user_id: str) -> bool:
        """检查用户是否完成了信息收集"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        return user.profile_completed

    def get_user_profile(self, db: Session, user_id: str) -> Optional[Dict]:
        """获取用户信息"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        return {
            "nickname": user.nickname,
            "birth_year": user.birth_year,
            "hometown": user.hometown,
            "profile_completed": user.profile_completed
        }


profile_service = ProfileService()
