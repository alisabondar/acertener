import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base, created_at_column, one_of, uuid_pk

USER_ROLES = ("provider", "nurse", "front_desk", "admin")
CREDENTIALS = ("MD", "DO", "NP", "PA", "RN", "LPN", "MA")


class User(Base):
    """Staff account. Login fields are filled in by the auth provider."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    credential: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_developer: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        CheckConstraint(one_of("role", USER_ROLES), name="role"),
        CheckConstraint(
            f"credential IS NULL OR {one_of('credential', CREDENTIALS)}", name="credential"
        ),
    )
