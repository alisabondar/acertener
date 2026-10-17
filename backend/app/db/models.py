import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import EncryptedDate, EncryptedText

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

PATIENT_STATUSES = ("active", "inactive", "deceased")
ARCHIVE_REASONS = ("entered_in_error", "duplicate", "other")


def _one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

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

    birth_year: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    last_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    archive_reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))

    # SQLAlchemy reads this per class; ClassVar would clash with its own declaration.
    __mapper_args__ = {"version_id_col": version}  # noqa: RUF012
    __table_args__ = (
        # Leftmost prefix also serves last-name-only search.
        Index(None, "last_name_fp", "dob_fp"),
        CheckConstraint(_one_of("status", PATIENT_STATUSES), name="status"),
        CheckConstraint(
            f"archive_reason IS NULL OR {_one_of('archive_reason', ARCHIVE_REASONS)}",
            name="archive_reason",
        ),
    )
