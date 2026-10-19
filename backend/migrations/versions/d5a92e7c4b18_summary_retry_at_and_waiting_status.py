"""keep the AI provider's retry time apart from chart edits

Revision ID: d5a92e7c4b18
Revises: c3f81a7d2b90
Create Date: 2026-10-19 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5a92e7c4b18"
down_revision: str | Sequence[str] | None = "c3f81a7d2b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = ("fresh", "stale", "generating", "failed", "blocked")
AFTER = ("fresh", "stale", "waiting", "generating", "failed", "blocked")


def _allow(statuses: tuple[str, ...]) -> None:
    # The naming convention adds the "ck_patient_summaries_" prefix to "status".
    op.drop_constraint("status", "patient_summaries", type_="check")
    allowed = ", ".join(f"'{value}'" for value in statuses)
    op.create_check_constraint("status", "patient_summaries", f"status IN ({allowed})")


def upgrade() -> None:
    op.add_column(
        "patient_summaries", sa.Column("retry_at", sa.DateTime(timezone=True), nullable=True)
    )
    _allow(AFTER)


def downgrade() -> None:
    op.execute("UPDATE patient_summaries SET status = 'stale' WHERE status = 'waiting'")
    _allow(BEFORE)
    op.drop_column("patient_summaries", "retry_at")
