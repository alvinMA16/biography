# 干预判断 - 对话停滞
# 检测对话是否停滞、需要换角度

PROMPT = """判断对话是否停滞，需要换角度切入。

## 最近对话
{recent_messages}

## 用户刚说的
{user_message}

## 判断标准
以下情况说明对话可能停滞了：
- 连续几轮对话在同一个点上打转，没有新信息
- 用户反复说类似的内容，没有展开
- 对话陷入了"问-答-问-答"的机械循环，没有深入

如果对话停滞了，请输出引导建议，告诉记录师可以换什么角度来重新激活对话。
如果对话进展正常、有新信息产出，输出 null。

注意：对话刚开始几轮不算停滞，至少需要 4-5 轮对话后才判断是否停滞。

## 输出格式（JSON）
{{"guidance": "引导建议文本" 或 null}}

只输出 JSON，不要其他内容。"""


def build(recent_messages: str, user_message: str) -> str:
    """构建对话停滞判断的 prompt"""
    return PROMPT.format(
        recent_messages=recent_messages,
        user_message=user_message
    )
