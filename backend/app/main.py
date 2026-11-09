from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.books import router as books_router
from app.api.health import router as health_router
from app.api.search import router as search_router
from app.book_cards import BookCardBuilder
from app.book_refresh import BookRefresh
from app.cache import JsonCache, make_redis
from app.config import get_settings
from app.daily_budget import DailyBudget
from app.db import make_engine
from app.http_client import make_http_client
from app.repository import SearchRepository
from app.search_cache import SearchCache
from app.usage import BudgetTransport, UsageGuards


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize resources here
    settings = get_settings()
    app.state.engine = make_engine(settings.database_url, echo=settings.sql_echo)
    app.state.redis = make_redis(settings.redis_url)
    app.state.daily_budget = DailyBudget(app.state.engine, settings.daily_ai_call_cap)
    app.state.usage = UsageGuards(
        app.state.redis, settings.daily_ai_call_cap, daily=app.state.daily_budget
    )
    app.state.search_cache = SearchCache(JsonCache(app.state.redis), settings.llm_model)
    app.state.model_http = httpx.AsyncClient(transport=BudgetTransport(app.state.usage))
    app.state.http = make_http_client(cache=app.state.search_cache.cache)
    app.state.book_cards = BookCardBuilder(app.state.http)
    app.state.repository = SearchRepository(app.state.engine)
    app.state.book_refresh = BookRefresh(
        app.state.repository,
        app.state.http,
        app.state.redis,
        settings.google_books_api_key,
    )

    yield  # This is where the application runs

    # Clean up resources here
    await app.state.http.aclose()
    await app.state.model_http.aclose()
    await app.state.redis.aclose()
    await app.state.engine.dispose()


app = FastAPI(title="Lumen API", version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(search_router)
app.include_router(books_router)
