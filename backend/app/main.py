from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.cache import make_redis
from app.config import get_settings
from app.db import make_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize resources here
    settings = get_settings()
    app.state.engine = make_engine(settings.database_url, echo=settings.sql_echo)
    app.state.redis = make_redis(settings.redis_url)

    yield  # This is where the application runs

    # Clean up resources here
    await app.state.redis.aclose()
    await app.state.engine.dispose()


app = FastAPI(title="Lumen API", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
