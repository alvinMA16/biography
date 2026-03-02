"""add gender to users

Revision ID: 4b7c2d3e5f6a
Revises: 316c4cfae7ea
Create Date: 2026-03-02 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b7c2d3e5f6a'
down_revision: Union[str, None] = '316c4cfae7ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('gender', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'gender')
