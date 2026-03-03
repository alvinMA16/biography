# 干预判断 - 时代记忆触发
# 知识注入型：输出背景知识而非行为指令

PROMPT = """判断是否需要注入时代背景知识来帮助引导对话。

## 用户刚说的
{user_message}

## 可用的时代记忆
{era_memories}

## 判断标准
如果用户提到了与时代相关的内容（特定年份、历史时期、时代特征的事物），而时代记忆中有相关背景，就提取出来。

需要注入时，提取与用户话题最相关的时代背景知识，用简洁的2-3句话描述。
不需要注入时输出 null。

## 输出格式（JSON）
{{"guidance": "相关的时代背景知识" 或 null}}

只输出 JSON。"""


def build(user_message: str, era_memories: str) -> str:
    return PROMPT.format(
        user_message=user_message,
        era_memories=era_memories or "（暂无时代记忆）",
    )
