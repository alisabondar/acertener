"""create users, care teams, visits, vitals

Revision ID: 5cada61cf702
Revises: 8248c875331a
Create Date: 2026-10-17 10:30:09.600791

"""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5cada61cf702"
down_revision: str | Sequence[str] | None = "8248c875331a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[uuid.UUID]:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def _fk(name: str, nullable: bool = False) -> sa.Column[uuid.UUID]:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _created_at() -> sa.Column[datetime]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "users",
        _id(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("credential", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_developer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _created_at(),
        sa.CheckConstraint(
            "role IN ('provider', 'nurse', 'front_desk', 'admin')", name=op.f("ck_users_role")
        ),
        sa.CheckConstraint(
            "credential IS NULL OR credential IN ('MD', 'DO', 'NP', 'PA', 'RN', 'LPN', 'MA')",
            name=op.f("ck_users_credential"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_foreign_key(
        op.f("fk_patients_archived_by_users"), "patients", "users", ["archived_by"], ["id"]
    )
    op.create_index(op.f("ix_patients_birth_year"), "patients", ["birth_year"])
    op.create_index(op.f("ix_patients_last_visit_at"), "patients", ["last_visit_at"])

    op.create_table(
        "care_team_members",
        _id(),
        _fk("patient_id"),
        _fk("user_id"),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "role IN ('primary_provider', 'provider', 'nurse')",
            name=op.f("ck_care_team_members_role"),
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], name=op.f("fk_care_team_members_patient_id_patients")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_care_team_members_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_care_team_members")),
    )
    op.create_index(
        op.f("ix_care_team_members_user_id_patient_id"),
        "care_team_members",
        ["user_id", "patient_id"],
        unique=True,
        postgresql_where=sa.text("end_date IS NULL"),
    )

    op.create_table(
        "visits",
        _id(),
        _fk("patient_id"),
        _fk("provider_id"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),  # EncryptedText
        _created_at(),
        sa.CheckConstraint(
            "status IN ('scheduled', 'checked_in', 'completed', 'no_show', 'cancelled')",
            name=op.f("ck_visits_status"),
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], name=op.f("fk_visits_patient_id_patients")
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"], ["users.id"], name=op.f("fk_visits_provider_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visits")),
    )
    op.create_index(op.f("ix_visits_scheduled_at"), "visits", ["scheduled_at"])
    op.create_index(
        op.f("ix_visits_patient_id_scheduled_at"), "visits", ["patient_id", "scheduled_at"]
    )

    op.create_table(
        "vitals",
        _id(),
        _fk("patient_id"),
        _fk("visit_id", nullable=True),
        _fk("recorded_by"),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        *(
            sa.Column(name, sa.SmallInteger(), nullable=True)
            for name in ("bp_systolic", "bp_diastolic", "heart_rate", "respiratory_rate", "spo2")
        ),
        sa.Column("temperature_c", sa.Numeric(4, 1), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 1), nullable=True),
        sa.Column("height_cm", sa.Numeric(5, 1), nullable=True),
        sa.ForeignKeyConstraint(
            ["patient_id"], ["patients.id"], name=op.f("fk_vitals_patient_id_patients")
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by"], ["users.id"], name=op.f("fk_vitals_recorded_by_users")
        ),
        sa.ForeignKeyConstraint(
            ["visit_id"], ["visits.id"], name=op.f("fk_vitals_visit_id_visits")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vitals")),
    )
    op.create_index(op.f("ix_vitals_patient_id_taken_at"), "vitals", ["patient_id", "taken_at"])


def downgrade() -> None:
    op.drop_table("vitals")
    op.drop_table("visits")
    op.drop_table("care_team_members")
    op.drop_index(op.f("ix_patients_last_visit_at"), table_name="patients")
    op.drop_index(op.f("ix_patients_birth_year"), table_name="patients")
    op.drop_constraint(op.f("fk_patients_archived_by_users"), "patients", type_="foreignkey")
    op.drop_table("users")
