"""initial empty schema

Revision ID: f0b9a4a033c5
Revises:
Create Date: 2026-10-16 14:52:21.346920

"""

from collections.abc import Sequence

revision: str = "f0b9a4a033c5"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
