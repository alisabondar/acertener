import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, created_at_column, one_of, uuid_pk
from app.db.types import EncryptedText

CARE_TEAM_ROLES = ("primary_provider", "provider", "nurse")
VISIT_STATUSES = ("scheduled", "checked_in", "completed", "no_show", "cancelled")


class CareTeamMember(Base):
    """Who looks after a patient. Ended memberships are kept as history."""

    __tablename__ = "care_team_members"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    end_date: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        # One active membership per user per patient; also serves the "My patients" lookup.
        Index(
            None, "user_id", "patient_id", unique=True, postgresql_where=text("end_date IS NULL")
        ),
        CheckConstraint(one_of("role", CARE_TEAM_ROLES), name="role"),
    )


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"))
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'scheduled'"))
    reason: Mapped[str | None] = mapped_column(EncryptedText)
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        Index(None, "patient_id", "scheduled_at"),
        CheckConstraint(one_of("status", VISIT_STATUSES), name="status"),
    )


class Vital(Base):
    """One set of measurements. Values are plaintext in encryption v1; all are optional."""

    __tablename__ = "vitals"

    id: Mapped[uuid.UUID] = uuid_pk()
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patients.id"))
    visit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visits.id"))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bp_systolic: Mapped[int | None] = mapped_column(SmallInteger)
    bp_diastolic: Mapped[int | None] = mapped_column(SmallInteger)
    heart_rate: Mapped[int | None] = mapped_column(SmallInteger)
    respiratory_rate: Mapped[int | None] = mapped_column(SmallInteger)
    spo2: Mapped[int | None] = mapped_column(SmallInteger)
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))

    __table_args__ = (Index(None, "patient_id", "taken_at"),)
