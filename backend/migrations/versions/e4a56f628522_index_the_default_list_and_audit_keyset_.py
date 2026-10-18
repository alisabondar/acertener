"""index the default list and audit keyset paging

Revision ID: e4a56f628522
Revises: 337564f24226
Create Date: 2026-10-17 15:35:57.028009

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4a56f628522"
down_revision: str | Sequence[str] | None = "337564f24226"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_patients_current_by_last_visit",
        "patients",
        [sa.text("last_visit_at DESC NULLS LAST"), "id"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.drop_index(op.f("ix_audit_log_patient_id_occurred_at"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_actor_id_occurred_at"), table_name="audit_log")
    op.create_index(op.f("ix_audit_log_patient_id_id"), "audit_log", ["patient_id", "id"])
    op.create_index(op.f("ix_audit_log_actor_id_id"), "audit_log", ["actor_id", "id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_actor_id_id"), table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_patient_id_id"), table_name="audit_log")
    op.create_index(
        op.f("ix_audit_log_actor_id_occurred_at"), "audit_log", ["actor_id", "occurred_at"]
    )
    op.create_index(
        op.f("ix_audit_log_patient_id_occurred_at"), "audit_log", ["patient_id", "occurred_at"]
    )
    op.drop_index("ix_patients_current_by_last_visit", table_name="patients")
