from fastapi import APIRouter, Request
from sqlalchemy import select

from app.auth.identity import CurrentUser, require_demo_mode
from app.auth.permissions import permissions_for
from app.db.models import User
from app.db.session import DbSession
from app.demo.personas import PERSONAS
from app.schemas.users import MeOut, UserOut

router = APIRouter(tags=["auth"])


@router.get("/auth/me")
async def me(user: CurrentUser) -> MeOut:
    return MeOut(**UserOut.model_validate(user).model_dump(), permissions=permissions_for(user))


@router.get("/personas")
async def personas(request: Request, session: DbSession) -> list[UserOut]:
    """The demo "View as" choices, in display order. Demo mode only."""
    require_demo_mode(request)
    order = [p.email for p in PERSONAS]
    users = await session.scalars(
        select(User).where(User.email.in_(order), User.is_active.is_(True))
    )
    return [UserOut.model_validate(u) for u in sorted(users, key=lambda u: order.index(u.email))]
