"""track when a summary generation started

Revision ID: b7d2e19c4f30
Revises: e4a56f628522
Create Date: 2026-10-19 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2e19c4f30"
down_revision: str | Sequence[str] | None = "e4a56f628522"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Lets a generation that never finished (a crash mid-request) be retried after a timeout.
    op.add_column(
        "patient_summaries",
        sa.Column("generation_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("patient_summaries", "generation_started_at")
