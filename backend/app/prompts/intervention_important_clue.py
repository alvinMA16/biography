# 干预判断 - 重要线索
# 检测用户是否提到了值得深挖的重要信息

PROMPT = """判断用户是否提到了值得深挖的重要线索。

## 用户刚说的
{user_message}

## 最近对话（作为上下文参考）
{recent_messages}

## 判断标准
以下类型的信息是值得深挖的重要线索：
- 具体的人物（家人、朋友、老师、同事等）
- 具体的地点（老家、学校、工作单位等）
- 具体的事件（搬家、换工作、重要经历等）
- 具体的时间节点（某一年发生的事）

如果发现重要线索，请输出引导建议，告诉记录师应该围绕这个线索追问什么。
如果没有特别值得深挖的线索，输出 null。

注意：不是每句话都有重要线索，只有真正值得深挖的才输出建议。

## 输出格式（JSON）
{{"guidance": "引导建议文本" 或 null}}

只输出 JSON，不要其他内容。"""


def build(recent_messages: str, user_message: str) -> str:
    """构建重要线索判断的 prompt"""
    return PROMPT.format(
        recent_messages=recent_messages,
        user_message=user_message
    )
