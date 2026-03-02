# 干预判断 - 话题偏离
# 检测对话是否偏离了"挖掘人生回忆"的目标

PROMPT = """判断对话是否偏离了"挖掘人生回忆"的目标。

## 本次话题
{topic}

## 最近对话
{recent_messages}

## 用户刚说的
{user_message}

## 判断标准
回忆录的目标是挖掘用户的人生故事、人物关系、情感体验。

如果发现以下情况，说明话题偏离了：
- 在某个具体事物上展开太久（如一直讨论某道菜怎么做、某个物件的细节）
- 对话变成了闲聊，没有在挖掘回忆
- 助手的问题没有指向人、事、情

如果话题偏离了，请输出引导建议，告诉记录师应该怎么把话题拉回来。
如果对话正常，输出 null。

## 输出格式（JSON）
{{"guidance": "引导建议文本" 或 null}}

只输出 JSON，不要其他内容。"""


def build(topic: str, recent_messages: str, user_message: str) -> str:
    """构建话题偏离判断的 prompt"""
    return PROMPT.format(
        topic=topic or "自由聊天",
        recent_messages=recent_messages,
        user_message=user_message
    )
