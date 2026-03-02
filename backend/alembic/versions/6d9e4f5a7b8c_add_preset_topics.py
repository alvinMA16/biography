"""add preset_topics table

Revision ID: 6d9e4f5a7b8c
Revises: 5c8d3e4f6a7b
Create Date: 2026-03-03 10:00:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d9e4f5a7b8c'
down_revision: Union[str, None] = '5c8d3e4f6a7b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 预设初始话题
PRESET_TOPICS = [
    {
        'topic': '成长与家庭',
        'greeting': '我们来聊聊你成长的家庭吧：你的父母（或主要照顾你的人）大概是什么样的人？你有没有兄弟姐妹或一起长大的亲人？你小时候家里的日常和氛围通常是怎样的？',
        'chat_context': (
            '追问路径：\n'
            '1. 你小时候在家里更像什么\u201c位置/角色\u201d？（被照顾、照顾人、很独立、负责沟通、比较安静等）\n'
            '2. 你和家人的关系在成长过程中有没有明显变化？大概是哪些阶段？（比如更亲近/更疏远/重新理解）\n'
            '3. 你觉得这个家庭对你影响最大的是什么？（价值观、性格习惯、对安全感的理解、处理情绪/冲突的方式）\n\n'
            '核心想知道：原生家庭画像 + 关系变化时间线 + 家庭如何塑造了\u201c现在的你\u201d。'
        ),
        'age_start': 0,
        'age_end': 18,
        'sort_order': 0,
    },
    {
        'topic': '最难熬的时期',
        'greeting': '如果你愿意，我们聊聊你人生里最难熬的一段时期：那段时间大概发生了什么（说轮廓就好）？你当时是怎么把日子过下去的？你靠什么撑住/调整？这段经历后来给你带来了哪些变化？',
        'chat_context': (
            '追问路径：\n'
            '1. 那段时期最难的点主要是什么？（压力、失去、关系、工作、健康、长期消耗等）\n'
            '2. 你当时最有效的\u201c应对方式\u201d是什么？（一个习惯/一个人/一个念头/一次决定）\n'
            '3. 走出来之后，你在哪些方面变了？（对自己、更看重什么、边界感、安全感、自我价值感）\n\n'
            '核心想知道：困难的类型 + 克服方式/资源 + 产生的改变。'
        ),
        'age_start': None,
        'age_end': None,
        'sort_order': 1,
    },
    {
        'topic': '人生的转折点',
        'greeting': '想聊聊你人生里一个\u201c转折点\u201d吗？它可能是你做的选择，也可能是某件事突然发生。那是什么？它让你的生活在哪些方面发生了变化？你当时是怎么应对、怎么做判断的？后来它对你留下了什么影响？',
        'chat_context': (
            '追问路径：\n'
            '1. 转折发生前 vs 发生后，最明显的变化是什么？（生活状态/关系/工作/心态）\n'
            '2. 当时你最纠结的是什么？你最后抓住了什么原则/信念？\n'
            '3. 回头看，这个转折让你学到的最重要的一点是什么？\n\n'
            '核心想知道：事件性质（主动/被动）+ 前后变化 + 当时的应对逻辑 + 长期影响。'
        ),
        'age_start': None,
        'age_end': None,
        'sort_order': 2,
    },
]


def upgrade() -> None:
    table = op.create_table(
        'preset_topics',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('topic', sa.String(200), nullable=False),
        sa.Column('greeting', sa.Text(), nullable=False),
        sa.Column('chat_context', sa.Text(), nullable=True),
        sa.Column('age_start', sa.Integer(), nullable=True),
        sa.Column('age_end', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 插入预设话题
    from datetime import datetime
    now = datetime.utcnow()
    op.bulk_insert(table, [
        {
            'id': str(uuid.uuid4()),
            'topic': t['topic'],
            'greeting': t['greeting'],
            'chat_context': t['chat_context'],
            'age_start': t['age_start'],
            'age_end': t['age_end'],
            'is_active': True,
            'sort_order': t['sort_order'],
            'created_at': now,
            'updated_at': now,
        }
        for t in PRESET_TOPICS
    ])


def downgrade() -> None:
    op.drop_table('preset_topics')
