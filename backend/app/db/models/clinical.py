import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, created_at_column, one_of, updated_at_column, uuid_pk
from app.db.types import EncryptedText

RECORD_STATUSES = ("active", "resolved", "entered_in_error")
ALLERGY_SEVERITIES = ("mild", "moderate", "severe")
NOTE_STATUSES = ("draft", "final")
SUMMARY_STATUSES = ("fresh", "stale", "waiting", "generating", "failed", "blocked")


class Allergy(Base):
    """Coded allergy detail is plaintext in encryption v1; status changes replace deletes."""

    __tablename__ = "allergies"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    substance: Mapped[str] = mapped_column(Text)
    reaction: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    __table_args__ = (
        CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),
        CheckConstraint(
            f"severity IS NULL OR {one_of('severity', ALLERGY_SEVERITIES)}", name="severity"
        ),
    )


class Condition(Base):
    __tablename__ = "conditions"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), index=True)
    icd10_code: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    onset_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    __table_args__ = (CheckConstraint(one_of("status", RECORD_STATUSES), name="status"),)


class Note(Base):
    """Clinical note. Deletes are soft (`deleted_at`), and only by the author."""

    __tablename__ = "notes"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    encounter_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content: Mapped[str] = mapped_column(EncryptedText)
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amends_note_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("notes.id"))
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    __table_args__ = (
        Index(None, "patient_id", "encounter_at"),
        CheckConstraint(one_of("status", NOTE_STATUSES), name="status"),
        CheckConstraint("status = 'draft' OR finalized_at IS NOT NULL", name="final_has_time"),
    )


class PatientSummary(Base):
    """Cached AI summary, one per patient. `content` holds only de-identified model output."""

    __tablename__ = "patient_summaries"

    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    content: Mapped[str | None] = mapped_column(EncryptedText)
    status: Mapped[str] = mapped_column(Text, server_default=text("'stale'"))
    input_hash: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(Text)
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the AI provider said it will take another request; separate from chart edits.
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint(one_of("status", SUMMARY_STATUSES), name="status"),)
