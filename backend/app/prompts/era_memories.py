# 生成时代记忆
# 根据用户出生年份和地点生成不同人生阶段的时代记忆参考

PROMPT = """用户出生于{birth_year}年，{location_info}。今年是{current_year}年，用户大约{age}岁。

请为这位用户生成不同人生阶段的时代记忆参考，这些记忆将帮助记录师在对话中唤起用户的回忆。

## 要求
- 每个阶段列出 4-6 个可能引起共鸣的记忆点
- 包括但不限于：流行音乐、歌手、电视剧、电影、综艺节目、品牌、零食、游戏、社会风潮、重大事件
- 内容要符合那个年代的真实情况
- 如果有地域特色的内容（比如地方电视台节目、当地品牌），可以加入
- 用简洁的关键词或短语，不需要详细解释

## 输出格式

童年（{childhood_start}-{childhood_end}岁，约{childhood_year_start}-{childhood_year_end}年）：
- xxx
- xxx
...

少年（{youth_start}-{youth_end}岁，约{youth_year_start}-{youth_year_end}年）：
- xxx
- xxx
...

青年（{young_start}-{young_end}岁，约{young_year_start}-{young_year_end}年）：
- xxx
- xxx
...

中年（{middle_start}-{middle_end}岁，约{middle_year_start}-{middle_year_end}年）：
- xxx
- xxx
...

（如果用户年龄超过50岁，继续添加后续阶段）

请直接输出内容，不要有其他说明。"""


def build(birth_year: int, hometown: str = None, main_city: str = None) -> str:
    """构建生成时代记忆的 prompt"""
    import datetime
    current_year = datetime.datetime.now().year
    age = current_year - birth_year

    # 构建地点信息
    location_info = ""
    if hometown and main_city:
        if hometown == main_city:
            location_info = f"家乡和主要生活城市都是{hometown}"
        else:
            location_info = f"家乡是{hometown}，生活时间最长的城市是{main_city}"
    elif hometown:
        location_info = f"家乡是{hometown}"
    elif main_city:
        location_info = f"主要生活在{main_city}"

    return PROMPT.format(
        birth_year=birth_year,
        location_info=location_info,
        current_year=current_year,
        age=age,
        # 童年 6-12 岁
        childhood_start=6, childhood_end=12,
        childhood_year_start=birth_year + 6, childhood_year_end=birth_year + 12,
        # 少年 12-18 岁
        youth_start=12, youth_end=18,
        youth_year_start=birth_year + 12, youth_year_end=birth_year + 18,
        # 青年 18-30 岁
        young_start=18, young_end=30,
        young_year_start=birth_year + 18, young_year_end=birth_year + 30,
        # 中年 30-50 岁
        middle_start=30, middle_end=50,
        middle_year_start=birth_year + 30, middle_year_end=birth_year + 50,
    )
