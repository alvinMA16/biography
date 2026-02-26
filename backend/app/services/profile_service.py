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
from app.services.topic_service import topic_service


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
        from app.prompts import profile_extraction
        prompt = profile_extraction.build(conversation_text)

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

            if result.get("main_city"):
                user.main_city = result["main_city"]
                updated = True

            # 无论是否完成，只要有更新就保存
            if updated:
                db.commit()
                print(f"[Profile] 已保存用户信息: nickname={user.nickname}, birth_year={user.birth_year}, hometown={user.hometown}, main_city={user.main_city}")

            # 如果有出生年份且时代记忆未生成，触发异步生成
            should_generate_era = (
                user.birth_year and
                user.era_memories_status in ('none', 'pending', 'failed')
            )

            # 如果收集到了足够信息，标记为完成
            if result.get("has_enough_info") or user.nickname:
                user.profile_completed = True
                db.commit()
                print(f"[Profile] 用户信息收集完成")

                # 生成初始开场白
                greeting_service.generate_initial_greetings(db, user)

                # 生成初始话题选项
                topic_service.generate_topic_options(db, user)

                # 异步生成时代记忆
                if should_generate_era:
                    self._generate_era_memories_async(user.id, user.birth_year, user.hometown, user.main_city)

                return True
            else:
                print(f"[Profile] 信息不足，未标记为完成，但已保存部分信息")
                # 即使未完成，只要有 birth_year 也生成时代记忆
                if should_generate_era:
                    print(f"[Profile] 有出生年份，触发时代记忆生成")
                    self._generate_era_memories_async(user.id, user.birth_year, user.hometown, user.main_city)
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
            "main_city": user.main_city,
            "profile_completed": user.profile_completed,
            "era_memories": user.era_memories
        }

    def _generate_era_memories_async(self, user_id: str, birth_year: int, hometown: str = None, main_city: str = None):
        """异步生成时代记忆"""
        import threading

        def _generate():
            from app.database import SessionLocal
            from app.services.llm_service import llm_service

            db = SessionLocal()
            try:
                # 标记为生成中
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.era_memories_status = 'generating'
                    db.commit()

                print(f"[Profile] 开始为用户 {user_id} 生成时代记忆...")
                era_memories = llm_service.generate_era_memories(birth_year, hometown, main_city)

                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.era_memories = era_memories
                    user.era_memories_status = 'completed'
                    db.commit()
                    print(f"[Profile] 时代记忆生成完成，已保存")
                else:
                    print(f"[Profile] 用户不存在: {user_id}")
            except Exception as e:
                print(f"[Profile] 生成时代记忆失败: {e}")
                import traceback
                traceback.print_exc()
                # 标记为失败
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        user.era_memories_status = 'failed'
                        db.commit()
                except:
                    pass
            finally:
                db.close()

        thread = threading.Thread(target=_generate)
        thread.start()

    def regenerate_era_memories(self, db: Session, user_id: str) -> Optional[str]:
        """重新生成时代记忆（同步）"""
        from app.services.llm_service import llm_service

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        if not user.birth_year:
            return None

        # 标记为生成中
        user.era_memories_status = 'generating'
        db.commit()

        try:
            print(f"[Profile] 为用户 {user_id} 重新生成时代记忆...")
            era_memories = llm_service.generate_era_memories(user.birth_year, user.hometown, user.main_city)
            user.era_memories = era_memories
            user.era_memories_status = 'completed'
            db.commit()
            print(f"[Profile] 时代记忆重新生成完成")
            return era_memories
        except Exception as e:
            print(f"[Profile] 重新生成时代记忆失败: {e}")
            user.era_memories_status = 'failed'
            db.commit()
            raise


profile_service = ProfileService()
