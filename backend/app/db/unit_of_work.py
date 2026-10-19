from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[None]:
    """Commit one write together with its audit entry (and side effects), or none of it.

    A savepoint (not session.rollback()) means a failure undoes only this write and leaves
    anything else in the session intact.
    """
    async with session.begin_nested():
        yield
    await session.commit()
