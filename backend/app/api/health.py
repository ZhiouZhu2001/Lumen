import asyncio
from collections.abc import Awaitable

from fastapi import APIRouter, Request, Response

from app.cache import check_redis
from app.db import check_postgres

router = APIRouter(prefix="/api")

CHECK_TIMEOUT_SECONDS = 2


async def _with_timeout(check: Awaitable[bool]) -> bool:
    try:
        return await asyncio.wait_for(check, timeout=CHECK_TIMEOUT_SECONDS)
    except TimeoutError:
        return False


@router.get("/health")
async def health_check(request: Request, response: Response) -> dict[str, str]:
    """
    Health check endpoint to verify the API is running.
    """
    state = request.app.state
    postgres_ok, redis_ok = await asyncio.gather(
        _with_timeout(check_postgres(state.engine)),
        _with_timeout(check_redis(state.redis)),
    )

    if not postgres_ok or not redis_ok:
        response.status_code = 503  # Service Unavailable

    return {
        "status": "ok" if postgres_ok and redis_ok else "down",
        "postgres": "ok" if postgres_ok else "down",
        "redis": "ok" if redis_ok else "down",
    }
