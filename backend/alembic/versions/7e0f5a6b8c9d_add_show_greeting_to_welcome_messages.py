"""add show_greeting to welcome_messages

Revision ID: 7e0f5a6b8c9d
Revises: 6d9e4f5a7b8c
Create Date: 2026-03-03 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e0f5a6b8c9d'
down_revision: Union[str, None] = '6d9e4f5a7b8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('welcome_messages',
        sa.Column('show_greeting', sa.Boolean(), server_default=sa.text('true'), nullable=False)
    )


def downgrade() -> None:
    op.drop_column('welcome_messages', 'show_greeting')
