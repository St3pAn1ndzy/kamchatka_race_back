"""merge heads

Revision ID: 86b3fe19a712
Revises: 5a6a8b3b19d3, 8280913ca1cf
Create Date: 2026-09-24 21:07:28.632281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86b3fe19a712'
down_revision: Union[str, Sequence[str], None] = ('5a6a8b3b19d3', '8280913ca1cf')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
