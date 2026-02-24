from openai import OpenAI
from typing import List, Dict
from app.config import settings


class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = settings.dashscope_model

    def chat(self, messages: List[Dict[str, str]], system_prompt: str = None) -> str:
        """发送对话请求到大模型"""
        full_messages = []

        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        full_messages.extend(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=0.8,
            max_tokens=500
        )

        return response.choices[0].message.content

    def generate_summary(self, conversation_text: str) -> str:
        """生成对话摘要"""
        from app.prompts import SUMMARY_PROMPT

        prompt = SUMMARY_PROMPT.format(conversation=conversation_text)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )

        return response.choices[0].message.content

    def generate_memoir(self, conversation_text: str, perspective: str = "第一人称") -> str:
        """生成回忆录内容"""
        from app.prompts import MEMOIR_PROMPT

        prompt = MEMOIR_PROMPT.format(
            conversation=conversation_text,
            perspective=perspective
        )
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )

        return response.choices[0].message.content


llm_service = LLMService()
