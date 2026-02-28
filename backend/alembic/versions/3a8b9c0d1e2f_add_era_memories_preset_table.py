"""add era memories preset table and topic age range

Revision ID: 3a8b9c0d1e2f
Revises: 2ef05eab1a27
Create Date: 2026-02-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a8b9c0d1e2f'
down_revision: Union[str, None] = '2ef05eab1a27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建预生成时代记忆表
    op.create_table('era_memories_preset',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('start_year', sa.Integer(), nullable=False),
        sa.Column('end_year', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # 给 topic_candidates 表添加 age_start 和 age_end 字段
    op.add_column('topic_candidates', sa.Column('age_start', sa.Integer(), nullable=True))
    op.add_column('topic_candidates', sa.Column('age_end', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('topic_candidates', 'age_end')
    op.drop_column('topic_candidates', 'age_start')
    op.drop_table('era_memories_preset')
