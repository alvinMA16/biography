# 生成对话摘要
# 将对话内容总结成简短摘要

PROMPT = """请根据以下对话内容，生成一个简短的摘要（50-100字），概括这次对话的主要内容：

{conversation}

摘要："""


def build(conversation: str) -> str:
    """构建生成摘要的 prompt"""
    return PROMPT.format(conversation=conversation)
