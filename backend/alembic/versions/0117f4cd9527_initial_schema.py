"""initial schema

Revision ID: 0117f4cd9527
Revises:
Create Date: 2026-02-27 21:41:26.464999

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0117f4cd9527'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('nickname', sa.String(32), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('birth_year', sa.Integer(), nullable=True),
        sa.Column('hometown', sa.String(100), nullable=True),
        sa.Column('main_city', sa.String(100), nullable=True),
        sa.Column('profile_completed', sa.Boolean(), nullable=True),
        sa.Column('era_memories', sa.Text(), nullable=True),
        sa.Column('era_memories_status', sa.String(20), nullable=True),
    )

    op.create_table(
        'conversations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(100), nullable=True),
        sa.Column('topic', sa.String(50), nullable=True),
        sa.Column('topics', sa.JSON(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=False),
        sa.Column('role', sa.String(10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'memoirs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('conversation_id', sa.String(36), sa.ForeignKey('conversations.id'), nullable=True),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('source_conversations', sa.JSON(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=True),
        sa.Column('year_start', sa.Integer(), nullable=True),
        sa.Column('year_end', sa.Integer(), nullable=True),
        sa.Column('time_period', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'topic_candidates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('topic', sa.String(200), nullable=False),
        sa.Column('greeting', sa.Text(), nullable=False),
        sa.Column('chat_context', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    op.create_table(
        'greeting_candidates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('topic', sa.String(50), nullable=True),
        sa.Column('context', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('greeting_candidates')
    op.drop_table('topic_candidates')
    op.drop_table('memoirs')
    op.drop_table('messages')
    op.drop_table('conversations')
    op.drop_table('users')
