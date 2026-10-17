import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, created_at_column, one_of, updated_at_column, uuid_pk
from app.db.types import EncryptedDate, EncryptedText

PATIENT_STATUSES = ("active", "inactive", "deceased")
ARCHIVE_REASONS = ("entered_in_error", "duplicate", "other")


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = uuid_pk()

    first_name: Mapped[str] = mapped_column(EncryptedText)
    last_name: Mapped[str] = mapped_column(EncryptedText)
    mrn: Mapped[str] = mapped_column(EncryptedText)
    dob: Mapped[date] = mapped_column(EncryptedDate)
    gender: Mapped[str | None] = mapped_column(EncryptedText)
    phone: Mapped[str | None] = mapped_column(EncryptedText)
    email: Mapped[str | None] = mapped_column(EncryptedText)
    address_line1: Mapped[str | None] = mapped_column(EncryptedText)
    address_line2: Mapped[str | None] = mapped_column(EncryptedText)
    city: Mapped[str | None] = mapped_column(EncryptedText)
    state: Mapped[str | None] = mapped_column(EncryptedText)
    postal_code: Mapped[str | None] = mapped_column(EncryptedText)

    last_name_fp: Mapped[bytes] = mapped_column(LargeBinary)
    dob_fp: Mapped[bytes] = mapped_column(LargeBinary, index=True)
    mrn_fp: Mapped[bytes] = mapped_column(LargeBinary, unique=True)

    birth_year: Mapped[int] = mapped_column(SmallInteger, index=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    archive_reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))

    # SQLAlchemy reads this per class; ClassVar would clash with its own declaration.
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        # Leftmost prefix also serves last-name-only search.
        Index(None, "last_name_fp", "dob_fp"),
        CheckConstraint(one_of("status", PATIENT_STATUSES), name="status"),
        CheckConstraint(
            f"archive_reason IS NULL OR {one_of('archive_reason', ARCHIVE_REASONS)}",
            name="archive_reason",
        ),
    )


class PatientNamePrefix(Base):
    """Blind index: one fingerprint per name prefix, so encrypted names can be prefix-searched."""

    __tablename__ = "patient_name_prefixes"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"), primary_key=True
    )
    purpose: Mapped[str] = mapped_column(Text, primary_key=True)
    fp: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)

    __table_args__ = (Index(None, "purpose", "fp"),)
