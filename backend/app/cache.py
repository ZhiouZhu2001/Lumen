from redis.asyncio import Redis

def make_redis(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)

async def check_redis(client: Redis) -> bool:
    try:
        return await client.ping()
    except Exception as e:
        return False
        