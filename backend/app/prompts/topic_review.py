# 审查和更新话题池
# 在用户完成一次对话后，检查现有话题是否仍然合适

PROMPT = """你是一位人生故事记录师的助手，需要审查和更新用户的话题候选池。

## 用户信息
{user_profile}

## 时代记忆
{era_memories}

## 用户所有回忆录摘要
{all_memoirs}

## 当前话题候选池
{current_topics}

## 任务
审查当前话题候选池，根据用户已有的回忆录内容，决定每个话题应该：
- **保留**：话题还没聊过或还有深入空间
- **删除**：话题已经充分聊过，不需要再聊
- **更新**：话题方向需要调整（比如从"童年"调整为"童年的某个具体方面"）

同时，如果发现有新的值得聊的话题，可以新增。

## 审查原则
1. 避免重复：如果某个话题已经深入聊过，应该删除或调整方向
2. 保持多样性：话题池应该覆盖不同的人生阶段和主题
3. 循序渐进：可以根据已聊内容，发现更深入的话题
4. 总数控制：话题池保持 6-10 个话题

## 输出格式（JSON）
{{
    "actions": [
        {{
            "action": "keep",
            "topic_id": "现有话题的ID"
        }},
        {{
            "action": "delete",
            "topic_id": "要删除的话题ID",
            "reason": "删除原因"
        }},
        {{
            "action": "update",
            "topic_id": "要更新的话题ID",
            "new_topic": "新的话题描述（5-10字）",
            "new_greeting": "新的开场白（50-100字）",
            "new_context": "新的对话背景信息（100-300字）"
        }},
        {{
            "action": "add",
            "topic": "新话题描述（5-10字）",
            "greeting": "开场白（50-100字）",
            "context": "对话背景信息（100-300字）"
        }}
    ]
}}

## 话题描述的要求
- 简短（5-10字）、中性、宽泛
- 不要预设情感色彩（温暖、幸福、难忘等）

## 只输出 JSON，不要其他内容
"""


def build(
    user_profile: str,
    era_memories: str,
    all_memoirs: str,
    current_topics: str
) -> str:
    """构建话题审查的 prompt"""
    if not era_memories or era_memories.strip() == "":
        era_memories = "（暂无时代记忆）"

    if not all_memoirs or all_memoirs.strip() == "":
        all_memoirs = "（暂无回忆录）"

    if not current_topics or current_topics.strip() == "":
        current_topics = "（话题池为空）"

    return PROMPT.format(
        user_profile=user_profile,
        era_memories=era_memories,
        all_memoirs=all_memoirs,
        current_topics=current_topics
    )
