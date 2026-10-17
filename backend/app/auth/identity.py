import uuid
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.db.session import get_session
from app.errors import NotAuthenticatedError

PERSONA_HEADER = "X-Persona"


def require_demo_mode(request: Request) -> None:
    if not request.app.state.settings.demo_mode:
        raise NotAuthenticatedError


async def current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    persona: Annotated[str | None, Header(alias=PERSONA_HEADER)] = None,
) -> User:
    """The only place identity is decided. In the MVP it's the demo persona from X-Persona;
    real login would replace this function's body, not its callers."""
    require_demo_mode(request)
    if persona is None:
        raise NotAuthenticatedError
    try:
        user_id = uuid.UUID(persona)
    except ValueError:
        raise NotAuthenticatedError from None
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise NotAuthenticatedError
    return user


CurrentUser = Annotated[User, Depends(current_user)]
