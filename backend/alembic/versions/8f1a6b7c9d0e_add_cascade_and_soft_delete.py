"""add cascade constraints and soft delete columns

Revision ID: 8f1a6b7c9d0e
Revises: 7e0f5a6b8c9d
Create Date: 2026-03-03 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1a6b7c9d0e'
down_revision: Union[str, None] = '7e0f5a6b8c9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Add ondelete CASCADE/SET NULL to foreign keys ---

    # conversations.user_id → CASCADE
    op.drop_constraint('conversations_user_id_fkey', 'conversations', type_='foreignkey')
    op.create_foreign_key(
        'conversations_user_id_fkey', 'conversations', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # messages.conversation_id → CASCADE
    op.drop_constraint('messages_conversation_id_fkey', 'messages', type_='foreignkey')
    op.create_foreign_key(
        'messages_conversation_id_fkey', 'messages', 'conversations',
        ['conversation_id'], ['id'], ondelete='CASCADE'
    )

    # memoirs.user_id → CASCADE
    op.drop_constraint('memoirs_user_id_fkey', 'memoirs', type_='foreignkey')
    op.create_foreign_key(
        'memoirs_user_id_fkey', 'memoirs', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # memoirs.conversation_id → SET NULL
    op.drop_constraint('memoirs_conversation_id_fkey', 'memoirs', type_='foreignkey')
    op.create_foreign_key(
        'memoirs_conversation_id_fkey', 'memoirs', 'conversations',
        ['conversation_id'], ['id'], ondelete='SET NULL'
    )

    # topic_candidates.user_id → CASCADE
    op.drop_constraint('topic_candidates_user_id_fkey', 'topic_candidates', type_='foreignkey')
    op.create_foreign_key(
        'topic_candidates_user_id_fkey', 'topic_candidates', 'users',
        ['user_id'], ['id'], ondelete='CASCADE'
    )

    # --- 2. Add deleted_at columns for soft delete ---

    op.add_column('users',
        sa.Column('deleted_at', sa.DateTime(), nullable=True)
    )
    op.add_column('conversations',
        sa.Column('deleted_at', sa.DateTime(), nullable=True)
    )
    op.add_column('memoirs',
        sa.Column('deleted_at', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    # Remove deleted_at columns
    op.drop_column('memoirs', 'deleted_at')
    op.drop_column('conversations', 'deleted_at')
    op.drop_column('users', 'deleted_at')

    # Restore foreign keys without ondelete
    op.drop_constraint('topic_candidates_user_id_fkey', 'topic_candidates', type_='foreignkey')
    op.create_foreign_key(
        'topic_candidates_user_id_fkey', 'topic_candidates', 'users',
        ['user_id'], ['id']
    )

    op.drop_constraint('memoirs_conversation_id_fkey', 'memoirs', type_='foreignkey')
    op.create_foreign_key(
        'memoirs_conversation_id_fkey', 'memoirs', 'conversations',
        ['conversation_id'], ['id']
    )

    op.drop_constraint('memoirs_user_id_fkey', 'memoirs', type_='foreignkey')
    op.create_foreign_key(
        'memoirs_user_id_fkey', 'memoirs', 'users',
        ['user_id'], ['id']
    )

    op.drop_constraint('messages_conversation_id_fkey', 'messages', type_='foreignkey')
    op.create_foreign_key(
        'messages_conversation_id_fkey', 'messages', 'conversations',
        ['conversation_id'], ['id']
    )

    op.drop_constraint('conversations_user_id_fkey', 'conversations', type_='foreignkey')
    op.create_foreign_key(
        'conversations_user_id_fkey', 'conversations', 'users',
        ['user_id'], ['id']
    )
