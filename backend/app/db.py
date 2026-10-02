from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from .config import get_settings
settings = get_settings()


def make_engine(database_url: str) -> AsyncEngine:
   return create_async_engine(database_url, pool_size=5, max_overflow=5, pool_pre_ping=True, echo=True)


check_postgres(engine)