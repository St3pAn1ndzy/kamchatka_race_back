"""official_mark

Revision ID: 46f06d62e70b
Revises: 3da3226b99bb
Create Date: 2026-09-27 18:36:33.582291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '46f06d62e70b'
down_revision: Union[str, Sequence[str], None] = '3da3226b99bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Убираем stage_id, делаем entered_by_admin_id обязательным."""
    # 1. entered_by_admin_id — NOT NULL (по брифу: отметку всегда вводит админ).
    op.alter_column(
        "official_marks",
        "entered_by_admin_id",
        existing_type=sa.INTEGER(),
        nullable=False,
    )

    # 2. Удаляем старый FK на stages и колонку stage_id (этап достаётся через checkpoint).
    op.drop_index(op.f("ix_official_marks_stage_id"), table_name="official_marks")
    op.drop_constraint(
        op.f("official_marks_stage_id_fkey"),
        "official_marks",
        type_="foreignkey",
    )
    op.drop_column("official_marks", "stage_id")

    # 3. Меняем FK на admin_accounts: SET NULL → RESTRICT.
    op.drop_constraint(
        op.f("official_marks_entered_by_admin_id_fkey"),
        "official_marks",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "official_marks_entered_by_admin_id_fkey",
        "official_marks",
        "admin_accounts",
        ["entered_by_admin_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Возвращаем stage_id и nullable=True."""
    # 1. Возвращаем FK на admin_accounts: RESTRICT → SET NULL.
    op.drop_constraint(
        "official_marks_entered_by_admin_id_fkey",
        "official_marks",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("official_marks_entered_by_admin_id_fkey"),
        "official_marks",
        "admin_accounts",
        ["entered_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 2. entered_by_admin_id — снова nullable.
    op.alter_column(
        "official_marks",
        "entered_by_admin_id",
        existing_type=sa.INTEGER(),
        nullable=True,
    )

    # 3. Возвращаем stage_id.
    op.add_column(
        "official_marks",
        sa.Column("stage_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )
    op.create_index(
        op.f("ix_official_marks_stage_id"),
        "official_marks",
        ["stage_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("official_marks_stage_id_fkey"),
        "official_marks",
        "stages",
        ["stage_id"],
        ["id"],
        ondelete="SET NULL",
    )