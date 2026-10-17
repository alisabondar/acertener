"""create patient name prefixes

Revision ID: 8248c875331a
Revises: a506af3563c2
Create Date: 2026-10-16 19:23:57.177218

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8248c875331a"
down_revision: str | Sequence[str] | None = "a506af3563c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "patient_name_prefixes",
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("fp", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            name=op.f("fk_patient_name_prefixes_patient_id_patients"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "patient_id", "purpose", "fp", name=op.f("pk_patient_name_prefixes")
        ),
    )
    op.create_index(
        op.f("ix_patient_name_prefixes_purpose_fp"), "patient_name_prefixes", ["purpose", "fp"]
    )


def downgrade() -> None:
    op.drop_table("patient_name_prefixes")
