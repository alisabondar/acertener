from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

CONNECT_TIMEOUT_SECONDS = 5


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"timeout": CONNECT_TIMEOUT_SECONDS},
    )
