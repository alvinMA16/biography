# 推断时间段
# 从对话内容推断回忆发生的大概时间段

PROMPT = """请根据以下对话内容，推断这段回忆发生的大概时间段。

{birth_info}

## 对话内容
{conversation}

## 推断规则
- 如果提到"幼儿园"，大概是 3-6 岁
- 如果提到"小学"，大概是 6-12 岁
- 如果提到"初中"，大概是 12-15 岁
- 如果提到"高中"，大概是 15-18 岁
- 如果提到"大学"，大概是 18-22 岁
- 如果提到具体年份或年龄，直接使用
- 如果用户出生年份已知，可以据此计算具体年份

## 输出格式（JSON）
{{
    "year_start": 开始年份（4位数字，如果无法推断则为 null）,
    "year_end": 结束年份（4位数字，如果是某一年则与 year_start 相同，无法推断则为 null）,
    "time_period": "时期描述（如：童年、小学时期、大学时期、工作初期等）"
}}

只输出 JSON，不要其他内容。"""


def build(conversation: str, birth_year: int = None) -> str:
    """构建推断时间段的 prompt"""
    birth_info = f"用户出生于 {birth_year} 年。" if birth_year else "用户出生年份未知。"
    return PROMPT.format(birth_info=birth_info, conversation=conversation)
