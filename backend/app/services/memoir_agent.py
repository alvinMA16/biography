"""
回忆录生成 Agent
通过多轮调用，让模型自己决定如何整理回忆录
"""
import json
from typing import Optional, List, Dict, Any
from openai import OpenAI
from app.config import settings


# Agent 可用的工具定义
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "analyze",
            "description": "分析访谈记录，识别主题、时间线和结构。在开始整理前先调用此工具理解内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "识别出的主题列表"
                    },
                    "timeline": {
                        "type": "string",
                        "description": "时间线概述（如果有的话）"
                    },
                    "structure_notes": {
                        "type": "string",
                        "description": "结构分析笔记，比如哪些内容需要聚合"
                    }
                },
                "required": ["topics", "structure_notes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "draft",
            "description": "输出回忆录草稿。可以多次调用来迭代改进。",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "回忆录草稿内容"
                    },
                    "notes": {
                        "type": "string",
                        "description": "关于这版草稿的说明，比如做了哪些处理"
                    }
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check",
            "description": "检查当前草稿的质量。对照原始访谈确认是否保留了所有重要内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "preserved_content": {
                        "type": "boolean",
                        "description": "是否保留了用户说的所有重要内容"
                    },
                    "kept_style": {
                        "type": "boolean",
                        "description": "是否保持了用户的语言风格"
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "发现的问题列表"
                    },
                    "needs_revision": {
                        "type": "boolean",
                        "description": "是否需要继续修改"
                    }
                },
                "required": ["preserved_content", "kept_style", "needs_revision"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "完成任务，输出最终的回忆录。只有当你确认质量满意时才调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "memoir": {
                        "type": "string",
                        "description": "最终的回忆录内容"
                    }
                },
                "required": ["memoir"]
            }
        }
    }
]


SYSTEM_PROMPT = """你是一位回忆录整理助手。你的任务是将用户的口述访谈整理成可读的回忆录。

## 你有以下工具可用

1. **analyze** - 分析访谈记录
   - 在开始前先调用，理解用户讲了什么
   - 识别主题、时间线、需要聚合的内容

2. **draft** - 输出草稿
   - 可以多次调用来迭代改进
   - 每次说明做了哪些处理

3. **check** - 检查质量
   - 对照原始访谈检查
   - 确认是否保留了所有重要内容
   - 确认是否保持了用户风格

4. **finish** - 完成任务
   - 只有确认满意后才调用
   - 输出最终回忆录

## 工作流程

1. 先用 analyze 分析访谈内容
2. 用 draft 输出第一版草稿
3. 用 check 检查质量
4. 如果有问题，用 draft 修改
5. 满意后用 finish 完成

## 整理原则

### 去除这些内容
- 记录师的提问和引导
- "问起..."、"聊到这里要忙了"等采访过程描述
- 重复的内容（保留说得更完整的那次）

### 整理结构
- 同一主题的内容放到一起（即使用户分开说的）
- 按时间顺序或逻辑顺序排列
- 段落之间自然过渡

### 润色程度
只做这些：
- 改错别字
- 让句子通顺（但不改变用词风格）
- 去掉多余的语气词（"嗯"、"那个"、"就是"）

### 绝对不要
- 不要添加用户没说的内容
- 不要把口语改成书面语
- 不要用"美好"、"珍贵"、"难忘"等空话
- 不要假设用户的年龄（用户可能是任何年龄）

## 叙述人称
使用{perspective}叙述。

---

现在请开始处理以下访谈记录：

{transcript}
"""


class MemoirAgent:
    """回忆录生成 Agent"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.dashscope_base_url
        )
        self.model = settings.dashscope_model
        self.max_iterations = 10  # 最大迭代次数，防止无限循环

    def generate(self, transcript: str, perspective: str = "第一人称") -> str:
        """
        生成回忆录

        Args:
            transcript: 访谈记录
            perspective: 叙述人称

        Returns:
            生成的回忆录内容
        """
        # 构建初始消息
        system_prompt = SYSTEM_PROMPT.format(
            perspective=perspective,
            transcript=transcript
        )

        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # Agent 主循环
        current_draft = ""
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            print(f"[MemoirAgent] 第 {iteration} 轮调用")

            try:
                # 调用模型
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.7,
                    max_tokens=4000
                )

                assistant_message = response.choices[0].message

                # 检查是否有工具调用
                if assistant_message.tool_calls:
                    # 处理工具调用
                    messages.append({
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in assistant_message.tool_calls
                        ]
                    })

                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)

                        print(f"[MemoirAgent] 调用工具: {tool_name}")

                        # 处理不同的工具
                        if tool_name == "analyze":
                            result = self._handle_analyze(tool_args)
                        elif tool_name == "draft":
                            current_draft = tool_args.get("content", "")
                            result = self._handle_draft(tool_args)
                        elif tool_name == "check":
                            result = self._handle_check(tool_args)
                        elif tool_name == "finish":
                            # 完成，返回最终结果
                            memoir = tool_args.get("memoir", current_draft)
                            print(f"[MemoirAgent] 完成，共 {iteration} 轮")
                            return memoir
                        else:
                            result = {"error": f"未知工具: {tool_name}"}

                        # 添加工具结果
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(result, ensure_ascii=False)
                        })

                else:
                    # 没有工具调用，可能是模型直接返回了内容
                    content = assistant_message.content
                    if content:
                        print(f"[MemoirAgent] 模型直接返回内容，共 {iteration} 轮")
                        return content
                    else:
                        # 空响应，提示继续
                        messages.append({
                            "role": "user",
                            "content": "请继续处理，使用工具完成任务。"
                        })

            except Exception as e:
                print(f"[MemoirAgent] 错误: {e}")
                import traceback
                traceback.print_exc()

                # 如果有草稿，返回草稿
                if current_draft:
                    return current_draft

                # 否则返回错误信息
                return f"（生成失败: {str(e)}）"

        # 达到最大迭代次数
        print(f"[MemoirAgent] 达到最大迭代次数 {self.max_iterations}")
        return current_draft if current_draft else "（生成超时）"

    def _handle_analyze(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理 analyze 工具调用"""
        topics = args.get("topics", [])
        timeline = args.get("timeline", "")
        notes = args.get("structure_notes", "")

        print(f"[MemoirAgent] 分析结果 - 主题: {topics}")

        return {
            "status": "ok",
            "message": f"已识别 {len(topics)} 个主题，请继续处理。"
        }

    def _handle_draft(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理 draft 工具调用"""
        content = args.get("content", "")
        notes = args.get("notes", "")

        word_count = len(content)
        print(f"[MemoirAgent] 草稿 - {word_count} 字, 说明: {notes[:50] if notes else '无'}...")

        return {
            "status": "ok",
            "word_count": word_count,
            "message": "草稿已保存，请用 check 工具检查质量，或用 finish 完成。"
        }

    def _handle_check(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理 check 工具调用"""
        preserved = args.get("preserved_content", False)
        kept_style = args.get("kept_style", False)
        issues = args.get("issues", [])
        needs_revision = args.get("needs_revision", False)

        print(f"[MemoirAgent] 检查 - 内容完整: {preserved}, 风格保持: {kept_style}, 需修改: {needs_revision}")

        if needs_revision:
            return {
                "status": "needs_revision",
                "message": f"发现 {len(issues)} 个问题，请用 draft 工具修改后再检查。"
            }
        else:
            return {
                "status": "ok",
                "message": "质量检查通过，可以用 finish 工具完成任务。"
            }


# 单例
memoir_agent = MemoirAgent()
