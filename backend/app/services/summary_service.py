"""
对话摘要服务
- 对话结束时生成摘要
- 提取主题标签
"""
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session
from openai import OpenAI
import json

from app.config import settings
from app.models import Conversation, Message


class SummaryService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = settings.dashscope_model

    def generate_summary(self, db: Session, conversation_id: str) -> Tuple[Optional[str], Optional[List[str]]]:
        """
        生成对话摘要和主题标签

        Returns:
            (summary, topics) - 摘要文本和主题列表
        """
        # 获取对话消息
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).all()

        if not messages:
            return None, None

        # 构建对话文本
        conversation_text = "\n".join([
            f"{'用户' if msg.role == 'user' else '记录师'}: {msg.content}"
            for msg in messages
        ])

        if len(conversation_text) < 50:
            return None, None

        prompt = f"""请分析以下访谈对话，生成摘要和主题标签。

## 对话内容
{conversation_text}

## 任务
1. 生成一段简短的摘要（50-100字），概括用户讲述了什么内容
2. 提取 1-5 个主题标签（如：童年、求学、工作、婚姻、家庭、爱好、困难时期、人生转折等）

## 输出格式（JSON）
{{
    "summary": "摘要内容...",
    "topics": ["主题1", "主题2", ...]
}}

只输出 JSON，不要其他内容。
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )

            content = response.choices[0].message.content.strip()

            # 解析 JSON
            # 处理可能的 markdown 代码块
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            summary = result.get("summary", "")
            topics = result.get("topics", [])

            print(f"[Summary] 生成摘要: {summary[:50]}...")
            print(f"[Summary] 主题标签: {topics}")

            # 更新数据库
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()

            if conversation:
                conversation.summary = summary
                conversation.topics = topics
                if topics:
                    conversation.topic = topics[0]  # 主要主题
                db.commit()

            return summary, topics

        except Exception as e:
            print(f"[Summary] 生成摘要失败: {e}")
            import traceback
            traceback.print_exc()
            return None, None


summary_service = SummaryService()
