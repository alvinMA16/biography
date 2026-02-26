# 生成回忆录标题
# 根据对话内容生成简练的标题

PROMPT = """请根据以下对话内容，生成一个简练的标题（5-15个字），概括这段回忆的主题。

要求：
- 标题要简洁有意境
- 突出回忆的核心内容或情感
- 不要用"回忆"、"故事"等泛泛的词
- 直接返回标题，不要有引号或其他格式

对话内容：
{conversation}

标题："""


def build(conversation: str) -> str:
    """构建生成标题的 prompt"""
    return PROMPT.format(conversation=conversation)
