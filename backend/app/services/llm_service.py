from typing import List, Dict, Generator
from app.services.llm_client import llm_chat, llm_chat_stream


class LLMService:
    def chat(self, messages: List[Dict[str, str]], system_prompt: str = None) -> str:
        """发送对话请求到大模型"""
        full_messages = []

        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        full_messages.extend(messages)

        response = llm_chat("summary", messages=full_messages, temperature=0.8, max_tokens=500)
        return response.content

    def chat_stream(self, messages: List[Dict[str, str]], system_prompt: str = None) -> Generator[str, None, None]:
        """流式对话请求"""
        full_messages = []

        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})

        full_messages.extend(messages)

        yield from llm_chat_stream("summary", messages=full_messages, temperature=0.8, max_tokens=500)

    def generate_summary(self, conversation_text: str) -> str:
        """生成对话摘要"""
        from app.prompts import summary

        prompt = summary.build(conversation_text)
        response = llm_chat("summary", messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=200)
        return response.content

    def generate_memoir(self, conversation_text: str, perspective: str = "第一人称") -> str:
        """生成回忆录内容"""
        from app.prompts import memoir

        prompt = memoir.build(conversation_text, perspective)
        response = llm_chat("memoir", messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=2000)
        return response.content

    def generate_title(self, conversation_text: str) -> str:
        """根据对话内容生成简练的标题"""
        from app.prompts import title

        prompt = title.build(conversation_text)
        response = llm_chat("memoir", messages=[{"role": "user", "content": prompt}], fast=True, temperature=0.7, max_tokens=30)
        return response.content.strip()

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
        from app.prompts import time_period

        prompt = time_period.build(conversation_text, birth_year)

        try:
            response = llm_chat("memoir", messages=[{"role": "user", "content": prompt}], fast=True, temperature=0.1, max_tokens=100)
            content = response.content.strip()

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

    def check_profile_completion(self, conversation_text: str) -> bool:
        """检查信息收集对话是否已收集全部 4 项信息（称呼、出生年份、家乡、主要城市）"""
        import json
        from app.prompts import profile_completion_check

        prompt = profile_completion_check.build(conversation_text)

        try:
            response = llm_chat("profile", messages=[{"role": "user", "content": prompt}], fast=True, temperature=0.1, max_tokens=50)
            content = response.content.strip()

            # 处理可能的 markdown 代码块
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            return result.get("complete", False)
        except Exception as e:
            print(f"[LLM] 信息收集完成度检查失败: {e}")
            # 出错时默认返回 True，避免阻塞用户
            return True

    def generate_era_memories(self, birth_year: int, hometown: str = None, main_city: str = None) -> str:
        """根据用户出生年份和地点生成时代记忆"""
        from app.prompts import era_memories

        prompt = era_memories.build(birth_year, hometown, main_city)
        response = llm_chat("profile", messages=[{"role": "user", "content": prompt}], temperature=0.7, max_tokens=2000)
        return response.content


llm_service = LLMService()
