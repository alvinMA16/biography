from openai import OpenAI
from typing import List, Dict, Generator
from app.config import settings


class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = settings.dashscope_model
        self.model_fast = settings.dashscope_model_fast  # 快速模型

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

    def chat_stream(self, messages: List[Dict[str, str]], system_prompt: str = None) -> Generator[str, None, None]:
        """流式对话请求"""
        full_messages = []

        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        full_messages.extend(messages)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=0.8,
            max_tokens=500,
            stream=True
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def generate_empathy(self, user_text: str) -> str:
        """生成共情回应（使用快速模型，不需要历史上下文）"""
        from app.prompts import EMPATHY_PROMPT

        response = self.client.chat.completions.create(
            model=self.model_fast,  # 使用快速模型
            messages=[
                {"role": "system", "content": EMPATHY_PROMPT},
                {"role": "user", "content": user_text}
            ],
            temperature=0.8,
            max_tokens=200  # 共情回应3-4句话
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
            max_tokens=2000  # 增加 token 限制，允许更详细的内容
        )

        return response.choices[0].message.content

    def generate_title(self, conversation_text: str) -> str:
        """根据对话内容生成简练的标题"""
        prompt = f"""请根据以下对话内容，生成一个简练的标题（5-15个字），概括这段回忆的主题。

要求：
- 标题要简洁有意境
- 突出回忆的核心内容或情感
- 不要用"回忆"、"故事"等泛泛的词
- 直接返回标题，不要有引号或其他格式

对话内容：
{conversation_text}

标题："""

        response = self.client.chat.completions.create(
            model=self.model_fast,  # 使用快速模型
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=30
        )

        return response.choices[0].message.content.strip()

    def infer_time_period(self, conversation_text: str, birth_year: int = None) -> dict:
        """
        从对话内容推断时间段

        Returns:
            {
                "year_start": 1985,  # 开始年份，可能为 None
                "year_end": 1990,    # 结束年份，可能为 None
                "time_period": "小学时期"  # 时期描述
            }
        """
        import json

        birth_info = f"用户出生于 {birth_year} 年。" if birth_year else "用户出生年份未知。"

        prompt = f"""请根据以下对话内容，推断这段回忆发生的大概时间段。

{birth_info}

## 对话内容
{conversation_text}

## 推断规则
- 如果提到"幼儿园"，大概是 3-6 岁
- 如果提到"小学"，大概是 6-12 岁
- 如果提到"初中"，大概是 12-15 岁
- 如果提到"高中"，大概是 15-18 岁
- 如果提到"大学"，大概是 18-22 岁
- 如果提到具体年份或年龄，直接使用
- 如果用户出生年份已知，可以据此计算具体年份

## 输出格式（JSON）
{{
    "year_start": 开始年份（4位数字，如果无法推断则为 null）,
    "year_end": 结束年份（4位数字，如果是某一年则与 year_start 相同，无法推断则为 null）,
    "time_period": "时期描述（如：童年、小学时期、大学时期、工作初期等）"
}}

只输出 JSON，不要其他内容。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model_fast,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100
            )

            content = response.choices[0].message.content.strip()

            # 处理可能的 markdown 代码块
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            return {
                "year_start": result.get("year_start"),
                "year_end": result.get("year_end"),
                "time_period": result.get("time_period", "")
            }
        except Exception as e:
            print(f"[LLM] 推断时间段失败: {e}")
            return {"year_start": None, "year_end": None, "time_period": ""}


llm_service = LLMService()
