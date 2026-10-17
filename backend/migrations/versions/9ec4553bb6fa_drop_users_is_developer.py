"""drop users.is_developer

Revision ID: 9ec4553bb6fa
Revises: 74ffde75776b
Create Date: 2026-10-17 11:21:53.434117

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9ec4553bb6fa"
down_revision: str | Sequence[str] | None = "74ffde75776b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The demo persona picker replaced the developer account, so the flag has no use.
    op.drop_column("users", "is_developer")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_developer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
