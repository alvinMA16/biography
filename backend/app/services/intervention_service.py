"""
干预判断服务
并行执行多个判断，在超时时间内返回的结果合并
"""
import json
import asyncio
from typing import List, Dict, Optional
from openai import AsyncOpenAI

from app.config import settings
from app.prompts import (
    intervention_topic_drift,
    intervention_important_clue,
    intervention_era_trigger,
    intervention_stagnation,
)


class InterventionService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        # 使用更快的模型做判断
        self.model = settings.dashscope_model_fast

    async def judge_and_intervene(
        self,
        topic: str,
        recent_messages: List[Dict],
        user_message: str,
        era_memories: str = "",
        timeout_ms: int = None
    ) -> Optional[str]:
        """
        并行执行多个干预判断，合并超时前返回的结果

        Args:
            topic: 本次对话话题
            recent_messages: 最近几轮对话 [{"role": "user/assistant", "content": "..."}]
            user_message: 用户刚说的话
            era_memories: 时代记忆（用于时代触发判断）
            timeout_ms: 超时时间（毫秒），默认使用配置

        Returns:
            合并后的干预引导文本，无需干预则返回 None
        """
        if not settings.intervention_enabled:
            return None

        if timeout_ms is None:
            timeout_ms = settings.intervention_timeout_ms

        # 格式化最近对话为文本
        recent_text = self._format_messages(recent_messages)

        # 创建并行任务
        tasks = [
            asyncio.create_task(
                self._judge_topic_drift(topic, recent_text, user_message),
                name="topic_drift"
            ),
            asyncio.create_task(
                self._judge_important_clue(recent_text, user_message),
                name="important_clue"
            ),
            asyncio.create_task(
                self._judge_era_trigger(user_message, era_memories),
                name="era_trigger"
            ),
            asyncio.create_task(
                self._judge_stagnation(recent_text, user_message),
                name="stagnation"
            ),
        ]

        print(f"[Intervention] 开始并行判断，超时 {timeout_ms}ms")

        # 等待所有任务完成或超时
        done, pending = await asyncio.wait(
            tasks,
            timeout=timeout_ms / 1000,
            return_when=asyncio.ALL_COMPLETED
        )

        # 取消未完成的任务
        for task in pending:
            task.cancel()
            print(f"[Intervention] 任务超时取消: {task.get_name()}")

        # 收集已完成的干预结果
        interventions = []
        for task in done:
            try:
                result = task.result()
                if result:
                    print(f"[Intervention] {task.get_name()} 需要干预: {result[:50]}...")
                    interventions.append(result)
                else:
                    print(f"[Intervention] {task.get_name()} 无需干预")
            except Exception as e:
                print(f"[Intervention] {task.get_name()} 异常: {e}")

        # 合并干预内容
        if interventions:
            merged = self._merge_interventions(interventions)
            print(f"[Intervention] 合并后的干预内容: {merged[:100]}...")
            return merged

        print("[Intervention] 所有判断完成，无需干预")
        return None

    def _format_messages(self, messages: List[Dict]) -> str:
        """格式化消息列表为文本"""
        if not messages:
            return "（暂无对话记录）"

        lines = []
        for msg in messages[-6:]:  # 只取最近 6 条
            role = "用户" if msg.get("role") == "user" else "记录师"
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _merge_interventions(self, interventions: List[str]) -> str:
        """合并多个干预引导"""
        if len(interventions) == 1:
            return interventions[0]

        # 多个干预时，组合成一条
        return "请注意以下几点：" + "；".join(interventions)

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """调用 LLM 进行判断"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )

            content = response.choices[0].message.content.strip()

            # 解析 JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            guidance = result.get("guidance")

            return guidance if guidance else None

        except json.JSONDecodeError as e:
            print(f"[Intervention] JSON 解析失败: {e}")
            return None
        except Exception as e:
            print(f"[Intervention] LLM 调用失败: {e}")
            return None

    async def _judge_topic_drift(self, topic: str, recent_messages: str, user_message: str) -> Optional[str]:
        """判断话题偏离"""
        prompt = intervention_topic_drift.build(topic, recent_messages, user_message)
        return await self._call_llm(prompt)

    async def _judge_important_clue(self, recent_messages: str, user_message: str) -> Optional[str]:
        """判断重要线索"""
        prompt = intervention_important_clue.build(recent_messages, user_message)
        return await self._call_llm(prompt)

    async def _judge_era_trigger(self, user_message: str, era_memories: str) -> Optional[str]:
        """判断时代触发"""
        if not era_memories:
            return None  # 没有时代记忆，跳过这个判断
        prompt = intervention_era_trigger.build(user_message, era_memories)
        return await self._call_llm(prompt)

    async def _judge_stagnation(self, recent_messages: str, user_message: str) -> Optional[str]:
        """判断对话停滞"""
        # 对话太短时不判断停滞
        if recent_messages.count("\n") < 6:  # 至少 3 轮对话
            return None
        prompt = intervention_stagnation.build(recent_messages, user_message)
        return await self._call_llm(prompt)


# 单例
intervention_service = InterventionService()
