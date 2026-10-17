import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.identity import CurrentUser, require_demo_mode
from app.db.models import User
from app.db.session import get_session
from app.demo.personas import PERSONAS

router = APIRouter(tags=["auth"])


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    role: str
    credential: str | None


@router.get("/auth/me")
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.get("/personas")
async def personas(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> list[UserOut]:
    """The demo "View as" choices, in display order. Demo mode only."""
    require_demo_mode(request)
    order = [p.email for p in PERSONAS]
    users = await session.scalars(
        select(User).where(User.email.in_(order), User.is_active.is_(True))
    )
    return [UserOut.model_validate(u) for u in sorted(users, key=lambda u: order.index(u.email))]
