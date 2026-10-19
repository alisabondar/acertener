"""add a patient's blood type

Revision ID: c3f81a7d2b90
Revises: b7d2e19c4f30
Create Date: 2026-10-19 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f81a7d2b90"
down_revision: str | Sequence[str] | None = "b7d2e19c4f30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BLOOD_TYPES = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")


def upgrade() -> None:
    op.add_column("patients", sa.Column("blood_type", sa.Text(), nullable=True))
    allowed = ", ".join(f"'{value}'" for value in BLOOD_TYPES)
    op.create_check_constraint(
        "blood_type", "patients", f"blood_type IS NULL OR blood_type IN ({allowed})"
    )


def downgrade() -> None:
    # The naming convention adds the "ck_patients_" prefix, as it did when the constraint was made.
    op.drop_constraint("blood_type", "patients", type_="check")
    op.drop_column("patients", "blood_type")
