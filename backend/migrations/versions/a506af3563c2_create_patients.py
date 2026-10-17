"""create patients

Revision ID: a506af3563c2
Revises: f0b9a4a033c5
Create Date: 2026-10-16 17:56:10.616471

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a506af3563c2"
down_revision: str | Sequence[str] | None = "f0b9a4a033c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    encrypted = sa.Text  # EncryptedText / EncryptedDate are TEXT holding "v1:..." ciphertext
    op.create_table(
        "patients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("first_name", encrypted(), nullable=False),
        sa.Column("last_name", encrypted(), nullable=False),
        sa.Column("mrn", encrypted(), nullable=False),
        sa.Column("dob", encrypted(), nullable=False),
        sa.Column("gender", encrypted(), nullable=True),
        sa.Column("phone", encrypted(), nullable=True),
        sa.Column("email", encrypted(), nullable=True),
        sa.Column("address_line1", encrypted(), nullable=True),
        sa.Column("address_line2", encrypted(), nullable=True),
        sa.Column("city", encrypted(), nullable=True),
        sa.Column("state", encrypted(), nullable=True),
        sa.Column("postal_code", encrypted(), nullable=True),
        sa.Column("last_name_fp", sa.LargeBinary(), nullable=False),
        sa.Column("dob_fp", sa.LargeBinary(), nullable=False),
        sa.Column("mrn_fp", sa.LargeBinary(), nullable=False),
        sa.Column("birth_year", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("archive_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'deceased')", name=op.f("ck_patients_status")
        ),
        sa.CheckConstraint(
            "archive_reason IS NULL OR "
            "archive_reason IN ('entered_in_error', 'duplicate', 'other')",
            name=op.f("ck_patients_archive_reason"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_patients")),
        sa.UniqueConstraint("mrn_fp", name=op.f("uq_patients_mrn_fp")),
    )
    op.create_index(op.f("ix_patients_dob_fp"), "patients", ["dob_fp"])
    op.create_index(op.f("ix_patients_last_name_fp_dob_fp"), "patients", ["last_name_fp", "dob_fp"])


def downgrade() -> None:
    op.drop_table("patients")
