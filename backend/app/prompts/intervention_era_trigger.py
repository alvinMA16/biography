# 干预判断 - 时代记忆触发
# 检测是否需要注入时代背景来引导对话

PROMPT = """判断是否需要注入时代背景来帮助引导对话。

## 用户刚说的
{user_message}

## 可用的时代记忆
{era_memories}

## 判断标准
如果用户提到了以下内容，可以从时代记忆中找到相关背景来引导：
- 特定的年份或年代（如"1970年"、"八十年代"）
- 历史时期或运动（如"下乡"、"改革开放"）
- 时代特征的事物（如"粮票"、"知青"、"国企改制"）

如果能从时代记忆中找到与用户提到的内容相关的背景，请输出引导建议，
告诉记录师可以用这些时代背景来引导用户回忆。

如果用户没有提到与时代相关的内容，或者时代记忆中没有相关信息，输出 null。

## 输出格式（JSON）
{{"guidance": "引导建议文本" 或 null}}

只输出 JSON，不要其他内容。"""


def build(user_message: str, era_memories: str) -> str:
    """构建时代触发判断的 prompt"""
    return PROMPT.format(
        user_message=user_message,
        era_memories=era_memories or "（暂无时代记忆）"
    )
