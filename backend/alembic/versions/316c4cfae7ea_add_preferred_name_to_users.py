"""add preferred_name to users

Revision ID: 316c4cfae7ea
Revises: 00a84b8534cf
Create Date: 2026-03-02 14:45:10.934096

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '316c4cfae7ea'
down_revision: Union[str, None] = '00a84b8534cf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('preferred_name', sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'preferred_name')
