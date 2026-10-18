import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base
from app.db.types import EncryptedText


class AuditLog(Base):
    """Append-only (a database trigger rejects UPDATE and DELETE).

    `patient_id` and `entity_id` have no foreign keys: an audit write must never fail
    because of another row, and audit history outlives the rows it describes.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    via_demo_persona: Mapped[bool] = mapped_column(Boolean)
    action: Mapped[str] = mapped_column(Text)
    entity: Mapped[str] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    request_id: Mapped[str | None] = mapped_column(Text)
    # JSON of field -> {"old", "new"}; values can be PHI, so it's encrypted.
    changes: Mapped[str | None] = mapped_column(EncryptedText)

    __table_args__ = (
        # Ordered by id (which follows time) to match the newest-first keyset paging.
        Index(None, "patient_id", "id"),
        Index(None, "actor_id", "id"),
    )
