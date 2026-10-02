from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from .config import get_settings
settings = get_settings()

def make_redis(redis_url: str):
    import aioredis
    return aioredis.from_url(redis_url, decode_responses=True)