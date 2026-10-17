"""create clinical record tables

Revision ID: 74ffde75776b
Revises: 5cada61cf702
Create Date: 2026-10-17 10:36:04.490097

"""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "74ffde75776b"
down_revision: str | Sequence[str] | None = "5cada61cf702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RECORD_STATUSES = "status IN ('active', 'resolved', 'entered_in_error')"


def _id() -> sa.Column[uuid.UUID]:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _uuid(name: str, nullable: bool = False) -> sa.Column[uuid.UUID]:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _timestamp(name: str, *, default_now: bool = False) -> sa.Column[datetime]:
    if default_now:
        return sa.Column(
            name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        )
    return sa.Column(name, sa.DateTime(timezone=True), nullable=True)


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}")
    )


def upgrade() -> None:
    op.create_table(
        "allergies",
        _id(),
        _uuid("patient_id"),
        sa.Column("substance", sa.Text(), nullable=False),
        sa.Column("reaction", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        _uuid("recorded_by"),
        _timestamp("created_at", default_now=True),
        _timestamp("updated_at", default_now=True),
        sa.CheckConstraint(RECORD_STATUSES, name=op.f("ck_allergies_status")),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('mild', 'moderate', 'severe')",
            name=op.f("ck_allergies_severity"),
        ),
        _fk("allergies", "patient_id", "patients"),
        _fk("allergies", "recorded_by", "users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allergies")),
    )
    op.create_index(op.f("ix_allergies_patient_id"), "allergies", ["patient_id"])

    op.create_table(
        "conditions",
        _id(),
        _uuid("patient_id"),
        sa.Column("icd10_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("onset_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        _uuid("recorded_by"),
        _timestamp("created_at", default_now=True),
        _timestamp("updated_at", default_now=True),
        sa.CheckConstraint(RECORD_STATUSES, name=op.f("ck_conditions_status")),
        _fk("conditions", "patient_id", "patients"),
        _fk("conditions", "recorded_by", "users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conditions")),
    )
    op.create_index(op.f("ix_conditions_patient_id"), "conditions", ["patient_id"])

    op.create_table(
        "notes",
        _id(),
        _uuid("patient_id"),
        _uuid("author_id"),
        sa.Column("encounter_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),  # EncryptedText
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        _timestamp("finalized_at"),
        _timestamp("deleted_at"),
        _uuid("deleted_by", nullable=True),
        _timestamp("signed_at"),
        _uuid("amends_note_id", nullable=True),
        _timestamp("created_at", default_now=True),
        _timestamp("updated_at", default_now=True),
        sa.CheckConstraint("status IN ('draft', 'final')", name=op.f("ck_notes_status")),
        sa.CheckConstraint(
            "status = 'draft' OR finalized_at IS NOT NULL", name=op.f("ck_notes_final_has_time")
        ),
        _fk("notes", "patient_id", "patients"),
        _fk("notes", "author_id", "users"),
        _fk("notes", "deleted_by", "users"),
        _fk("notes", "amends_note_id", "notes"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notes")),
    )
    op.create_index(
        op.f("ix_notes_patient_id_encounter_at"), "notes", ["patient_id", "encounter_at"]
    )

    op.create_table(
        "patient_summaries",
        _uuid("patient_id"),
        sa.Column("content", sa.Text(), nullable=True),  # EncryptedText
        sa.Column("status", sa.Text(), server_default=sa.text("'stale'"), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        _timestamp("generated_at"),
        _timestamp("source_changed_at"),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('fresh', 'stale', 'generating', 'failed', 'blocked')",
            name=op.f("ck_patient_summaries_status"),
        ),
        _fk("patient_summaries", "patient_id", "patients"),
        sa.PrimaryKeyConstraint("patient_id", name=op.f("pk_patient_summaries")),
    )


def downgrade() -> None:
    for table in ("patient_summaries", "notes", "conditions", "allergies"):
        op.drop_table(table)
