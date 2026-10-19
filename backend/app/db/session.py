from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One database session per request."""
    async with request.app.state.sessionmaker() as session:
        yield session


# "function" scope closes the session as soon as the endpoint returns, before the response and its
# background tasks. Background audit writes open their own connection, so holding this one too
# would let a busy pool deadlock, every request waiting on a second connection.
DbSession = Annotated[AsyncSession, Depends(get_session, scope="function")]
