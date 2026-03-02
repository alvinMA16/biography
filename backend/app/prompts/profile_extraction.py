# 提取用户信息
# 从对话中提取用户的基本信息（不包括姓名，姓名由管理员填写）

PROMPT = """请从以下对话中提取用户的基本信息。

## 对话内容
{conversation}

## 需要提取的信息
1. preferred_name - 用户希望被怎么称呼（如：老张、张爷爷、李阿姨、建国叔等）
   - 这是"称呼"，不是"姓名"
   - 如果用户说"叫我老张"、"叫我张爷爷"，提取"老张"、"张爷爷"
   - 如果用户说"我叫张建国"，这可能是在说姓名，不要提取（姓名已由管理员填写）
2. birth_year - 出生年份（4位数字，如：1950）
   - 如果用户确认了已知的年份，也要提取
   - 如果用户纠正了年份，提取用户说的新年份
3. hometown - 家乡或出生地（如：北京、山东济南等）
4. main_city - 生活时间最长的城市（如果和家乡一样就填一样的）

## 输出格式（JSON）
{{
    "preferred_name": "提取到的称呼，如果没有提到则为null",
    "birth_year": 提取到的年份数字，如果没有提到或只是确认则为null,
    "hometown": "提取到的地点，如果没有提到则为null",
    "main_city": "生活时间最长的城市，如果没有提到则为null",
    "has_enough_info": true或false（是否收集到了称呼信息）
}}

## 注意
- 不要提取姓名（nickname），姓名由管理员填写，不从对话中获取
- 只输出 JSON，不要其他内容
- 如果用户说了年龄，请根据当前年份（{current_year}年）计算出出生年份
"""


def build(conversation: str) -> str:
    """构建提取用户信息的 prompt"""
    import datetime
    current_year = datetime.datetime.now().year
    return PROMPT.format(conversation=conversation, current_year=current_year)
