"""
话题服务
- 为用户生成话题选项（含对话上下文）
- 对话结束后异步审查和更新话题池
- 获取话题选项供用户选择
"""
import json
import threading
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from openai import OpenAI

from app.config import settings
from app.models import User, TopicCandidate, Memoir
from app.services.era_memory_service import era_memory_service


class TopicService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = settings.dashscope_model

    def get_topic_options(self, db: Session, user_id: str) -> List[Dict]:
        """获取用户的话题选项（随机选取几个展示）"""
        candidates = db.query(TopicCandidate).filter(
            TopicCandidate.user_id == user_id
        ).all()

        if not candidates:
            return []

        # 随机选取展示（如果话题池较大）
        import random
        display_count = min(settings.topic_option_count, len(candidates))
        selected = random.sample(candidates, display_count)

        return [
            {
                "id": c.id,
                "topic": c.topic,
                "greeting": c.greeting,
                "context": c.chat_context or "",
                "age_start": c.age_start,
                "age_end": c.age_end
            }
            for c in selected
        ]

    def get_topic_by_id(self, db: Session, topic_id: str) -> Optional[TopicCandidate]:
        """根据ID获取话题"""
        return db.query(TopicCandidate).filter(TopicCandidate.id == topic_id).first()

    def generate_topic_options(self, db: Session, user: User) -> List[Dict]:
        """为用户首次生成话题选项"""
        from app.prompts import topic_options

        print(f"[Topic] 为用户 {user.id} 首次生成话题选项")

        # 构建用户画像
        profile = self._build_user_profile(user)

        # 获取时代记忆：优先用 preset 表，fallback 到用户个人时代记忆
        era_memories = ""
        if user.birth_year:
            era_memories = era_memory_service.get_for_user(db, user.birth_year)
        if not era_memories:
            era_memories = user.era_memories or ""

        prompt = topic_options.build(
            user_profile=profile,
            era_memories=era_memories,
            option_count=settings.topic_option_count
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8,
                max_tokens=3000
            )

            content = response.choices[0].message.content.strip()

            # 处理可能的 markdown 代码块
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            options = result.get("options", [])

            # 清空旧的，保存新的
            db.query(TopicCandidate).filter(
                TopicCandidate.user_id == user.id
            ).delete()

            saved_options = []
            for opt in options:
                candidate = TopicCandidate(
                    user_id=user.id,
                    topic=opt.get("topic", ""),
                    greeting=opt.get("greeting", ""),
                    chat_context=opt.get("context", ""),
                    age_start=opt.get("age_start"),
                    age_end=opt.get("age_end")
                )
                db.add(candidate)
                db.flush()
                saved_options.append({
                    "id": candidate.id,
                    "topic": candidate.topic,
                    "greeting": candidate.greeting,
                    "context": candidate.chat_context or "",
                    "age_start": candidate.age_start,
                    "age_end": candidate.age_end
                })

            db.commit()

            print(f"[Topic] 生成了 {len(saved_options)} 个话题选项")
            return saved_options

        except Exception as e:
            print(f"[Topic] 生成话题选项失败: {e}")
            import traceback
            traceback.print_exc()

            # 返回默认话题
            default_options = self._get_default_options()
            return self._save_default_options(db, user.id, default_options)

    def review_topic_pool_async(self, user_id: str):
        """异步审查和更新话题池（对话结束后调用）"""
        thread = threading.Thread(target=self._review_topic_pool_sync, args=(user_id,))
        thread.start()

    def _review_topic_pool_sync(self, user_id: str):
        """同步执行话题池审查"""
        from app.database import SessionLocal
        from app.prompts import topic_review

        db = SessionLocal()
        try:
            print(f"[Topic] 开始审查用户 {user_id} 的话题池")

            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                print(f"[Topic] 用户不存在: {user_id}")
                return

            # 获取现有话题
            candidates = db.query(TopicCandidate).filter(
                TopicCandidate.user_id == user_id
            ).all()

            # 构建审查所需的数据
            profile = self._build_user_profile(user)
            # 获取时代记忆：优先用 preset 表，fallback 到用户个人时代记忆
            era_memories = ""
            if user.birth_year:
                era_memories = era_memory_service.get_for_user(db, user.birth_year)
            if not era_memories:
                era_memories = user.era_memories or ""
            all_memoirs = self._get_all_memoirs_summary(db, user_id)
            current_topics = self._format_current_topics(candidates)

            prompt = topic_review.build(
                user_profile=profile,
                era_memories=era_memories,
                all_memoirs=all_memoirs,
                current_topics=current_topics
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=3000
            )

            content = response.choices[0].message.content.strip()

            # 处理可能的 markdown 代码块
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            actions = result.get("actions", [])

            # 执行审查结果
            self._apply_review_actions(db, user_id, candidates, actions)

            print(f"[Topic] 话题池审查完成，执行了 {len(actions)} 个操作")

        except Exception as e:
            print(f"[Topic] 话题池审查失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

    def _apply_review_actions(self, db: Session, user_id: str, candidates: List[TopicCandidate], actions: List[Dict]):
        """应用审查结果"""
        candidates_map = {c.id: c for c in candidates}

        for action in actions:
            action_type = action.get("action")

            if action_type == "keep":
                # 保留，不做任何操作
                pass

            elif action_type == "delete":
                topic_id = action.get("topic_id")
                if topic_id and topic_id in candidates_map:
                    db.delete(candidates_map[topic_id])
                    print(f"[Topic] 删除话题: {candidates_map[topic_id].topic}")

            elif action_type == "update":
                topic_id = action.get("topic_id")
                if topic_id and topic_id in candidates_map:
                    c = candidates_map[topic_id]
                    c.topic = action.get("new_topic", c.topic)
                    c.greeting = action.get("new_greeting", c.greeting)
                    c.chat_context = action.get("new_context", c.chat_context)
                    if "new_age_start" in action:
                        c.age_start = action.get("new_age_start")
                    if "new_age_end" in action:
                        c.age_end = action.get("new_age_end")
                    print(f"[Topic] 更新话题: {c.topic}")

            elif action_type == "add":
                new_candidate = TopicCandidate(
                    user_id=user_id,
                    topic=action.get("topic", ""),
                    greeting=action.get("greeting", ""),
                    chat_context=action.get("context", ""),
                    age_start=action.get("age_start"),
                    age_end=action.get("age_end")
                )
                db.add(new_candidate)
                print(f"[Topic] 新增话题: {new_candidate.topic}")

        db.commit()

    def _build_user_profile(self, user: User) -> str:
        """构建用户画像文本"""
        parts = []
        if user.nickname:
            parts.append(f"- 称呼: {user.nickname}")
        if user.birth_year:
            parts.append(f"- 出生年份: {user.birth_year}年")
        if user.hometown:
            parts.append(f"- 家乡: {user.hometown}")
        if user.main_city:
            parts.append(f"- 主要生活城市: {user.main_city}")

        return "\n".join(parts) if parts else "（暂无用户信息）"

    def _get_all_memoirs_summary(self, db: Session, user_id: str) -> str:
        """获取用户所有回忆录的简要摘要（用于审查）"""
        memoirs = db.query(Memoir).filter(
            Memoir.user_id == user_id,
            Memoir.status == "completed"
        ).order_by(Memoir.created_at.desc()).all()

        if not memoirs:
            return ""

        texts = []
        for m in memoirs:
            title = m.title or "无标题"
            # 只取前150字
            content = (m.content or "")[:150]
            if len(m.content or "") > 150:
                content += "..."
            texts.append(f"- {title}: {content}")

        return "\n".join(texts)

    def _format_current_topics(self, candidates: List[TopicCandidate]) -> str:
        """格式化当前话题列表"""
        texts = []
        for c in candidates:
            texts.append(f"- ID: {c.id}\n  话题: {c.topic}\n  开场白: {c.greeting[:50]}...")
        return "\n".join(texts)

    def _get_default_options(self) -> List[Dict]:
        """默认话题选项（LLM 生成失败时的兜底，只包含安全话题）"""
        return [
            {
                "topic": "小时候的家",
                "greeting": "今天想听您讲讲小时候住的地方。您小时候家里是什么样的？住在什么样的房子里？",
                "context": "这是首次对话，注意建立信任，节奏放慢。引导用户回忆童年居住环境。",
                "age_start": 0,
                "age_end": 12
            },
            {
                "topic": "上学那些年",
                "greeting": "今天想听您聊聊上学的事。您还记得小时候的学校是什么样的吗？",
                "context": "这是首次对话，注意建立信任，节奏放慢。引导用户回忆求学经历。",
                "age_start": 6,
                "age_end": 18
            },
            {
                "topic": "家乡的年味",
                "greeting": "今天想听您讲讲小时候过年的事。您小时候过年都有什么习俗？",
                "context": "这是首次对话，注意建立信任，节奏放慢。引导用户回忆节日传统和家乡风俗。",
                "age_start": 0,
                "age_end": 18
            },
            {
                "topic": "儿时的游戏",
                "greeting": "今天想听您聊聊小时候玩的事。您小时候最喜欢玩什么？和谁一起玩？",
                "context": "这是首次对话，注意建立信任，节奏放慢。引导用户回忆童年游戏和玩伴。",
                "age_start": 0,
                "age_end": 12
            },
        ]

    def _save_default_options(self, db: Session, user_id: str, options: List[Dict]) -> List[Dict]:
        """保存默认话题选项"""
        db.query(TopicCandidate).filter(
            TopicCandidate.user_id == user_id
        ).delete()

        saved_options = []
        for opt in options:
            candidate = TopicCandidate(
                user_id=user_id,
                topic=opt.get("topic", ""),
                greeting=opt.get("greeting", ""),
                chat_context=opt.get("context", ""),
                age_start=opt.get("age_start"),
                age_end=opt.get("age_end")
            )
            db.add(candidate)
            db.flush()
            saved_options.append({
                "id": candidate.id,
                "topic": candidate.topic,
                "greeting": candidate.greeting,
                "context": candidate.chat_context or "",
                "age_start": candidate.age_start,
                "age_end": candidate.age_end
            })

        db.commit()
        return saved_options


topic_service = TopicService()
