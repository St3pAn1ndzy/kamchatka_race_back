"""Align season uniqueness and add discipline server defaults.

Revision ID: e9b6e9a4457c
Revises: 793b4b11364c
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e9b6e9a4457c"
down_revision: str | Sequence[str] | None = "793b4b11364c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_seasons_year", table_name="seasons")
    op.create_unique_constraint("uq_seasons_year", "seasons", ["year"])
    op.alter_column(
        "disciplines",
        "sort_order",
        existing_type=sa.Integer(),
        server_default=sa.text("0"),
    )
    op.alter_column(
        "disciplines",
        "is_active",
        existing_type=sa.Boolean(),
        server_default=sa.text("true"),
    )


def downgrade() -> None:
    op.alter_column(
        "disciplines",
        "is_active",
        existing_type=sa.Boolean(),
        server_default=None,
    )
    op.alter_column(
        "disciplines",
        "sort_order",
        existing_type=sa.Integer(),
        server_default=None,
    )
    op.drop_constraint("uq_seasons_year", "seasons", type_="unique")
    op.create_index("ix_seasons_year", "seasons", ["year"], unique=True)
