"""Сохраняем исходную высоту точки маршрута при импорте"""

import sqlalchemy as sa
from alembic import op

revision = "b18c24a901ef"
down_revision = "7a5b09304c91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавляет необязательную высоту без изменения прежних маршрутов"""
    op.add_column("stage_route_points", sa.Column("elevation", sa.Float(), nullable=True))


def downgrade() -> None:
    """Удаляет столбец высоты, сохраняя координаты маршрута"""
    op.drop_column("stage_route_points", "elevation")
