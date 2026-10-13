"""Allow one active official mark per participant and checkpoint.

Revision ID: a5b1c2d3e4f5
Revises: 7d728253e82c
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a5b1c2d3e4f5"
down_revision: str | Sequence[str] | None = "7d728253e82c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT participant_id, checkpoint_id "
                "FROM official_marks WHERE is_cancelled = false "
                "GROUP BY participant_id, checkpoint_id HAVING count(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate is not None:
        raise RuntimeError(
            "Cannot add active official mark uniqueness: "
            f"participant_id={duplicate.participant_id}, "
            f"checkpoint_id={duplicate.checkpoint_id} has duplicates"
        )

    op.create_index(
        "uq_official_marks_active_participant_checkpoint",
        "official_marks",
        ["participant_id", "checkpoint_id"],
        unique=True,
        postgresql_where=sa.text("is_cancelled = false"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_official_marks_active_participant_checkpoint",
        table_name="official_marks",
    )
