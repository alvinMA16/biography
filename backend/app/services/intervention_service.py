"""
干预判断服务
并行执行多个判断，取最高优先级的一条结果
返回干预类型、注入机制、干预内容
"""
import json
import asyncio
from typing import List, Dict, Optional, Tuple
from openai import AsyncOpenAI

from app.config import settings
from app.prompts import (
    intervention_topic_drift,
    intervention_important_clue,
    intervention_era_trigger,
    intervention_stagnation,
)


# 干预类型
TYPE_TOPIC_DRIFT = "topic_drift"
TYPE_STAGNATION = "stagnation"
TYPE_IMPORTANT_CLUE = "important_clue"
TYPE_ERA_TRIGGER = "era_trigger"

# 注入机制
MECHANISM_INSTRUCTION = "instruction"  # 行为指令型（510 指令注入）
MECHANISM_KNOWLEDGE = "knowledge"      # 知识注入型（510 知识注入）

# 干预优先级（数字越小优先级越高）
# 重要线索最常用也最有价值，优先级最高
# 话题偏离应该很少触发（标准已收紧），优先级最低
PRIORITY = {
    TYPE_IMPORTANT_CLUE: 1,
    TYPE_STAGNATION: 2,
    TYPE_TOPIC_DRIFT: 3,
    TYPE_ERA_TRIGGER: 4,
}

# 类型中文名
TYPE_LABELS = {
    TYPE_TOPIC_DRIFT: "话题偏离",
    TYPE_STAGNATION: "对话停滞",
    TYPE_IMPORTANT_CLUE: "重要线索",
    TYPE_ERA_TRIGGER: "时代触发",
}

# 类型对应的注入机制
TYPE_MECHANISM = {
    TYPE_TOPIC_DRIFT: MECHANISM_INSTRUCTION,
    TYPE_STAGNATION: MECHANISM_INSTRUCTION,
    TYPE_IMPORTANT_CLUE: MECHANISM_INSTRUCTION,
    TYPE_ERA_TRIGGER: MECHANISM_KNOWLEDGE,
}


class InterventionService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = settings.intervention_model

    async def judge_and_intervene(
        self,
        topic: str,
        recent_messages: List[Dict],
        era_memories: str = "",
        timeout_ms: int = None
    ) -> Optional[Dict]:
        """
        并行执行多个干预判断，只取最高优先级的一条

        Args:
            topic: 话题背景（包含话题名 + 用户背景 + context）
            recent_messages: 最近几轮对话 [{"role": "user/assistant", "content": "..."}]
            era_memories: 时代记忆（用于时代触发判断）
            timeout_ms: 超时时间（毫秒）

        Returns:
            干预结果 dict，无需干预则返回 None
        """
        if not settings.intervention_enabled:
            return None

        if timeout_ms is None:
            timeout_ms = settings.intervention_timeout_ms

        # 格式化最近对话为文本（最近 8 条 = 4 轮）
        recent_text = self._format_messages(recent_messages)

        # 提取最后一条用户消息（用于时代触发判断）
        last_user_msg = ""
        for msg in reversed(recent_messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break

        # 创建并行任务
        tasks = [
            asyncio.create_task(
                self._judge_topic_drift(topic, recent_text),
                name=TYPE_TOPIC_DRIFT
            ),
            asyncio.create_task(
                self._judge_important_clue(topic, recent_text),
                name=TYPE_IMPORTANT_CLUE
            ),
            asyncio.create_task(
                self._judge_era_trigger(last_user_msg, era_memories),
                name=TYPE_ERA_TRIGGER
            ),
            asyncio.create_task(
                self._judge_stagnation(topic, recent_text),
                name=TYPE_STAGNATION
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
        timed_out_names = []
        for task in pending:
            task.cancel()
            timed_out_names.append(task.get_name())
            print(f"[Intervention] 任务超时取消: {task.get_name()}")

        # 收集已完成的干预结果
        results: List[Tuple[int, str, str]] = []  # (priority, type, guidance)
        for task in done:
            try:
                result = task.result()
                if result:
                    intervention_type = task.get_name()
                    guidance = result
                    priority = PRIORITY.get(intervention_type, 99)
                    print(f"[Intervention] {TYPE_LABELS.get(intervention_type)} 需要干预(优先级{priority}): {guidance[:50]}...")
                    results.append((priority, intervention_type, guidance))
                else:
                    print(f"[Intervention] {TYPE_LABELS.get(task.get_name(), task.get_name())} 无需干预")
            except Exception as e:
                print(f"[Intervention] {task.get_name()} 异常: {e}")

        # 只取最高优先级的一条
        if results:
            results.sort(key=lambda x: x[0])
            _, best_type, best_guidance = results[0]
            best_mechanism = TYPE_MECHANISM.get(best_type, MECHANISM_INSTRUCTION)
            best_label = TYPE_LABELS.get(best_type, best_type)

            print(f"[Intervention] 选择干预 [{best_label}|{best_mechanism}]: {best_guidance[:100]}...")
            return {
                "type": best_type,
                "type_label": best_label,
                "mechanism": best_mechanism,
                "guidance": best_guidance,
            }

        if timed_out_names:
            timed_out_labels = [TYPE_LABELS.get(n, n) for n in timed_out_names]
            print(f"[Intervention] 无需干预（{len(timed_out_names)}个任务超时: {', '.join(timed_out_labels)}）")
            return {
                "type": "timeout",
                "type_label": "判断超时",
                "mechanism": None,
                "guidance": None,
                "timed_out": timed_out_labels,
            }

        print("[Intervention] 所有判断完成，无需干预")
        return None

    def _format_messages(self, messages: List[Dict]) -> str:
        """格式化消息列表为文本（最近 8 条 = 4 轮对话）"""
        if not messages:
            return "（暂无对话记录）"

        lines = []
        for msg in messages[-8:]:
            role = "用户" if msg.get("role") == "user" else "访谈者"
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

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

    async def _judge_topic_drift(self, topic: str, recent_messages: str) -> Optional[str]:
        """判断话题偏离"""
        prompt = intervention_topic_drift.build(topic, recent_messages)
        return await self._call_llm(prompt)

    async def _judge_important_clue(self, topic: str, recent_messages: str) -> Optional[str]:
        """判断重要线索"""
        prompt = intervention_important_clue.build(topic, recent_messages)
        return await self._call_llm(prompt)

    async def _judge_era_trigger(self, user_message: str, era_memories: str) -> Optional[str]:
        """判断时代触发"""
        if not era_memories or not user_message:
            return None
        prompt = intervention_era_trigger.build(user_message, era_memories)
        return await self._call_llm(prompt)

    async def _judge_stagnation(self, topic: str, recent_messages: str) -> Optional[str]:
        """判断对话停滞"""
        # 对话太短时不判断停滞
        if recent_messages.count("\n") < 6:  # 至少 3 轮对话
            return None
        prompt = intervention_stagnation.build(recent_messages)
        return await self._call_llm(prompt)


# 单例
intervention_service = InterventionService()
