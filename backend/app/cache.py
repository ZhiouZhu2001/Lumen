import json
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


def make_redis(redis_url: str) -> Redis:
    return Redis.from_url(
        redis_url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
    )


class JsonCache:
    """Optional bounded caches fail open; mandatory usage guards do not."""

    def __init__(self, redis):
        self.redis = redis

    async def get(self, key):
        try:
            value = await self.redis.get(key)
            if value is None or len(value.encode()) > 2_000_000:
                return None
            return json.loads(value)
        except (RedisError, OSError, TimeoutError, ValueError, TypeError):
            return None

    async def put(self, key, value, ttl):
        try:
            payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if len(payload.encode()) <= 2_000_000:
                await self.redis.set(key, payload, ex=ttl)
        except (RedisError, OSError, TimeoutError, ValueError, TypeError):
            logger.warning("cache_write_unavailable")

    async def delete(self, key):
        try:
            await self.redis.delete(key)
        except (RedisError, OSError, TimeoutError):
            pass


async def check_redis(client: Redis) -> bool:
    try:
        return await client.ping()
    except Exception as e:  # noqa: BLE001 - any failure means "down"
        logger.warning("Redis health check failed: %s", e)
        return False
