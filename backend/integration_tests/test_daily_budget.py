import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.daily_budget import DailyBudget
from app.models import AIDailyUsage
from app.usage import UsageLimited, UsageUnavailable


async def initialized_budget(engine, cap=100, used=0):
    budget = DailyBudget(engine, cap)
    async with engine.connect() as connection:
        day, _ = await budget._clock(connection)
    await budget.raise_floor(used, expected_day=day)
    return budget


async def test_missing_ledger_fails_closed_until_explicitly_initialized(storage):
    _, engine = storage
    budget = DailyBudget(engine, 100)
    for method in [budget.check_daily, budget.consume_ai, budget.snapshot]:
        with pytest.raises(UsageUnavailable):
            await method()
    budget = await initialized_budget(engine, used=61)
    assert (await budget.snapshot())["used"] == 61


async def test_multiple_workers_share_an_atomic_persistent_limit(storage, redis_scope):
    _, engine = storage
    redis, prefix = redis_scope
    budget = await initialized_budget(engine, cap=10)
    workers = [budget, DailyBudget(engine, 10)]
    results = await asyncio.gather(
        *(workers[i % 2].consume_ai() for i in range(35)), return_exceptions=True
    )
    assert sum(r is None for r in results) == 10
    assert sum(isinstance(r, UsageLimited) and r.daily for r in results) == 25
    # Loss of disposable Redis data cannot grant another model allowance.
    await redis.set(prefix + ":temporary", "value")
    await redis.delete(prefix + ":temporary")
    assert (await DailyBudget(engine, 10).snapshot())["used"] == 10
    with pytest.raises(UsageLimited):
        await DailyBudget(engine, 10).consume_ai()


async def test_utc_rollover_uses_database_clock_and_only_one_singleton(storage):
    _, engine = storage
    budget = await initialized_budget(engine, cap=2, used=2)
    async with engine.begin() as connection:
        day, _ = await budget._clock(connection)
        await connection.execute(
            update(AIDailyUsage).values(utc_day=day - timedelta(days=1))
        )
    assert (await budget.snapshot())["used"] == 0
    await asyncio.gather(budget.consume_ai(), DailyBudget(engine, 2).consume_ai())
    assert (await budget.snapshot())["used"] == 2
    async with engine.connect() as connection:
        assert len((await connection.execute(select(AIDailyUsage.id))).all()) == 1


async def test_initialization_never_lowers_current_usage_and_unknown_time_fails_closed(
    storage,
):
    _, engine = storage
    budget = await initialized_budget(engine, used=61)
    async with engine.connect() as connection:
        day, _ = await budget._clock(connection)
    assert await budget.raise_floor(0, expected_day=day) == 61
    assert await budget.raise_floor(100, expected_day=day) == 100
    with pytest.raises(UsageLimited):
        await budget.consume_ai()
    with pytest.raises(ValueError):
        await budget.raise_floor(0, expected_day=day - timedelta(days=1))
    async with engine.begin() as connection:
        await connection.execute(
            update(AIDailyUsage).values(utc_day=day + timedelta(days=1))
        )
    with pytest.raises(UsageUnavailable):
        await budget.consume_ai()
    with pytest.raises(UsageUnavailable):
        await budget.check_daily()


async def test_database_failure_stops_before_any_provider_send(storage):
    import httpx
    from sqlalchemy.schema import DropTable

    from app.usage import BudgetTransport

    _, engine = storage
    budget = await initialized_budget(engine)
    assert engine.get_execution_options()["schema_translate_map"][None].startswith(
        "lumen_test_"
    )
    async with engine.begin() as connection:
        await connection.execute(DropTable(AIDailyUsage.__table__))
    calls = []
    async with httpx.AsyncClient(
        transport=BudgetTransport(
            budget, httpx.MockTransport(lambda r: calls.append(r))
        )
    ) as client:
        with pytest.raises(UsageUnavailable):
            await client.post("https://api.openai.com/v1/chat/completions")
    assert calls == []


@pytest.mark.parametrize("legacy", [None, 61])
async def test_admin_import_preserves_known_usage_and_blocks_missing_legacy_counter(
    storage, redis_scope, monkeypatch, legacy
):
    from types import SimpleNamespace

    from scripts import budget_admin

    _, engine = storage
    redis, prefix = redis_scope

    class ScopedRedis:
        async def time(self):
            return await redis.time()

        async def get(self, key):
            return await redis.get(prefix + ":" + key)

        async def aclose(self):
            pass

    seconds, _ = await redis.time()
    key = prefix + f":lumen:usage:v1:ai:{seconds // 86400}"
    if legacy is not None:
        await redis.set(key, legacy, ex=60)
    monkeypatch.setattr(
        budget_admin,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="isolated", redis_url="isolated", daily_ai_call_cap=100
        ),
    )
    monkeypatch.setattr(budget_admin, "make_engine", lambda _: engine)
    monkeypatch.setattr(budget_admin, "make_redis", lambda _: ScopedRedis())
    report = await budget_admin.administer(
        SimpleNamespace(mode="import-redis", used=None)
    )
    assert report["stored_used"] == (100 if legacy is None else 61)
    assert report["legacy_counter_present"] is (legacy is not None)
    assert await redis.get(key) == (None if legacy is None else "61")


async def test_rollback_export_raises_redis_floor_without_lowering_it(
    storage, redis_scope, monkeypatch
):
    from types import SimpleNamespace

    from scripts import budget_admin

    _, engine = storage
    redis, prefix = redis_scope
    await initialized_budget(engine, used=61)

    class ScopedRedis:
        async def time(self):
            return await redis.time()

        async def get(self, key):
            return await redis.get(prefix + ":" + key)

        async def eval(self, script, count, key, *args):
            return await redis.eval(script, count, prefix + ":" + key, *args)

        async def aclose(self):
            pass

    monkeypatch.setattr(
        budget_admin,
        "get_settings",
        lambda: SimpleNamespace(
            database_url="isolated", redis_url="isolated", daily_ai_call_cap=100
        ),
    )
    monkeypatch.setattr(budget_admin, "make_engine", lambda _: engine)
    monkeypatch.setattr(budget_admin, "make_redis", lambda _: ScopedRedis())
    args = SimpleNamespace(mode="export-redis-floor", used=None)
    report = await budget_admin.administer(args)
    assert report["stored_used"] == 61
    seconds, _ = await redis.time()
    key = prefix + f":lumen:usage:v1:ai:{seconds // 86400}"
    await redis.set(key, 80)
    report = await budget_admin.administer(args)
    assert report["stored_used"] == 80
    assert 0 < await redis.ttl(key) <= 86400
