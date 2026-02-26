# 提取用户信息
# 从对话中提取用户的基本信息

PROMPT = """请从以下对话中提取用户的基本信息。

## 对话内容
{conversation}

## 需要提取的信息
1. nickname - 用户希望被称呼的名字（如：张爷爷、李阿姨、老王等）
2. birth_year - 出生年份（4位数字，如：1950）
3. hometown - 家乡或出生地（如：北京、山东济南等）
4. main_city - 生活时间最长的城市（如果和家乡一样就填一样的）

## 输出格式（JSON）
{{
    "nickname": "提取到的称呼，如果没有提到则为null",
    "birth_year": 提取到的年份数字，如果没有提到则为null,
    "hometown": "提取到的地点，如果没有提到则为null",
    "main_city": "生活时间最长的城市，如果没有提到则为null",
    "has_enough_info": true或false（是否收集到了至少称呼信息）
}}

只输出 JSON，不要其他内容。如果用户说了年龄，请根据当前年份（{current_year}年）计算出出生年份。
"""


def build(conversation: str) -> str:
    """构建提取用户信息的 prompt"""
    import datetime
    current_year = datetime.datetime.now().year
    return PROMPT.format(conversation=conversation, current_year=current_year)
