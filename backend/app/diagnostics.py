"""Owned model resources for live teaching tools, sharing the production ledger."""

from contextlib import asynccontextmanager

import httpx

from app.config import get_settings
from app.daily_budget import DailyBudget
from app.db import make_engine
from app.llm import create_chat_model
from app.usage import BudgetTransport


@asynccontextmanager
async def diagnostic_model():
    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        budget = DailyBudget(engine, settings.daily_ai_call_cap)
        await budget.check_daily()
        async with httpx.AsyncClient(transport=BudgetTransport(budget)) as client:
            yield create_chat_model(http_client=client)
    finally:
        await engine.dispose()
