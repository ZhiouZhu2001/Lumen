from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI

from app.usage import UsageGuards, UsageLimited
from evals import http_run
from integration_tests.test_daily_budget import initialized_budget


async def test_hourly_isolation_preserves_existing_keys_and_one_shared_daily_budget(
    storage, redis_scope, monkeypatch
):
    _, engine = storage
    redis, prefix = redis_scope
    daily = await initialized_budget(engine, cap=1)
    guards = UsageGuards(redis, 1, namespace=prefix, daily=daily)
    for _ in range(20):
        await guards.admit_search("127.0.0.1")
    with pytest.raises(UsageLimited):
        await guards.admit_search("127.0.0.1")
    original_keys = [key async for key in redis.scan_iter(match=prefix + ":ip:*")]
    before = {key: await redis.get(key) for key in original_keys}
    app = FastAPI()
    app.state.daily_budget = daily
    app.state.usage = guards

    @asynccontextmanager
    async def fake_lifespan(_):
        yield

    monkeypatch.setattr(http_run, "lifespan", fake_lifespan)
    async with http_run.evaluation_lifespan(
        app, hourly_namespace=prefix + ":evaluation"
    ):
        assert app.state.usage.daily is app.state.daily_budget is daily
        await app.state.usage.admit_search("127.0.0.1")
        assert {key: await redis.get(key) for key in original_keys} == before
        await app.state.usage.consume_ai()
        replica = UsageGuards(redis, 1, namespace=prefix + ":other", daily=daily)
        with pytest.raises(UsageLimited):
            await replica.consume_ai()
        with pytest.raises(UsageLimited):
            await app.state.usage.consume_ai()
        assert (await daily.snapshot())["used"] == 1
