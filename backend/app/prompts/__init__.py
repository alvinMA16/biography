# Prompts 模块
# 所有 LLM 提示词都在这里管理

# 实时语音对话
from app.prompts import realtime_profile_collection  # 信息收集对话
from app.prompts import realtime_chat                # 正常回忆对话
from app.prompts import realtime_chat_enhanced       # 增强模式对话（精简版）
from app.prompts import dialog_examples              # 预设对话示例

# 干预判断
from app.prompts import intervention_topic_drift     # 话题偏离判断
from app.prompts import intervention_important_clue  # 重要线索判断
from app.prompts import intervention_era_trigger     # 时代触发判断
from app.prompts import intervention_stagnation      # 对话停滞判断

# 内容生成
from app.prompts import memoir            # 生成回忆录
from app.prompts import summary           # 生成摘要
from app.prompts import era_memories      # 生成时代记忆
from app.prompts import title             # 生成标题
from app.prompts import time_period       # 推断时间段
from app.prompts import topic_options     # 生成话题选项（含上下文）
from app.prompts import topic_review      # 审查和更新话题池
from app.prompts import profile_extraction  # 提取用户信息
