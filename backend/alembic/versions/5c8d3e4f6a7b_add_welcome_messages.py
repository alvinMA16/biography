"""add welcome_messages table

Revision ID: 5c8d3e4f6a7b
Revises: 4b7c2d3e5f6a
Create Date: 2026-03-02 22:00:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c8d3e4f6a7b'
down_revision: Union[str, None] = '4b7c2d3e5f6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 初始激励语
INITIAL_MESSAGES = [
    "每一段回忆，都是你留给家人最珍贵的礼物。",
    "您的故事，值得被记录和传承。",
    "今天，让我们一起翻开记忆的篇章。",
    "每个人的一生，都是一部值得书写的传奇。",
    "用声音留住岁月，让回忆温暖未来。",
]


def upgrade() -> None:
    table = op.create_table(
        'welcome_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 插入初始数据
    from datetime import datetime
    now = datetime.utcnow()
    op.bulk_insert(table, [
        {
            'id': str(uuid.uuid4()),
            'content': msg,
            'is_active': True,
            'sort_order': idx,
            'created_at': now,
            'updated_at': now,
        }
        for idx, msg in enumerate(INITIAL_MESSAGES)
    ])


def downgrade() -> None:
    op.drop_table('welcome_messages')
