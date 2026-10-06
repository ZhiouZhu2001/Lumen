import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)


def make_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    return create_async_engine(
        database_url, pool_size=5, max_overflow=5, pool_pre_ping=True, echo=echo
    )


async def check_postgres(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e: # noqa: BLE001 - any failure means "down"
        logger.warning("Postgres health check failed: %s", e)
        return False
