import logging

from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def make_redis(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)


async def check_redis(client: Redis) -> bool:
    try:
        return await client.ping()
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        return False
