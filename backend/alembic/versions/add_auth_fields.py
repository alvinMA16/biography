"""add auth fields to users

Revision ID: a1b2c3d4e5f6
Revises: 0117f4cd9527
Create Date: 2026-02-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '0117f4cd9527'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(128), nullable=True))
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='0'))
    op.create_index('ix_users_phone', 'users', ['phone'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_phone', table_name='users')
    op.drop_column('users', 'is_admin')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'phone')
