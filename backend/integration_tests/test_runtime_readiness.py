"""Actual read-only readiness over disposable PostgreSQL schemas and Redis."""

import json
from datetime import timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import insert, select

from app.config import Settings
from app.daily_budget import DailyBudget
from app.models import AIDailyUsage
from scripts.check_runtime_readiness import (
    VERSION_TABLE,
    expected_heads,
    inspect_runtime,
)


@pytest.mark.parametrize(
    "case,expected",
    [
        ("ready", "ready"),
        ("empty_budget", "not_ready"),
        ("future_budget", "not_ready"),
        ("exhausted", "cached_only"),
        ("old_budget", "ready"),
        ("missing_key", "not_ready"),
        ("blank_key", "not_ready"),
        ("changed_cap", "not_ready"),
        ("older_migration", "not_ready"),
        ("empty_version", "not_ready"),
        ("missing_version", "not_ready"),
    ],
)
async def test_actual_readiness_never_changes_usage_or_schema(
    storage, redis_scope, case, expected
):
    _, engine = storage
    redis, _ = redis_scope
    heads = expected_heads()
    settings = Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://test",
        redis_url="redis://test",
        openai_api_key=SecretStr("readiness-fixture-key"),
    )
    async with engine.begin() as connection:
        day, _ = await DailyBudget(engine, 100)._clock(connection)
        if case != "missing_version":
            await connection.run_sync(VERSION_TABLE.create)
            if case != "empty_version":
                await connection.execute(
                    insert(VERSION_TABLE),
                    [
                        {
                            "version_num": "older-fixture-head"
                            if case == "older_migration"
                            else head
                        }
                        for head in heads
                    ],
                )
        if case != "empty_budget":
            await connection.execute(
                insert(AIDailyUsage).values(
                    id=1,
                    utc_day=day
                    + timedelta(
                        days=1
                        if case == "future_budget"
                        else -1
                        if case == "old_budget"
                        else 0
                    ),
                    attempts=100 if case in {"exhausted", "old_budget"} else 7,
                )
            )
        before = (await connection.execute(select(AIDailyUsage))).all()
    if case in {"missing_key", "blank_key"}:
        settings.openai_api_key = SecretStr("   ") if case == "blank_key" else None
    if case == "changed_cap":
        settings.daily_ai_call_cap = 101
    keys = sorted([key async for key in redis.scan_iter()])
    report = await inspect_runtime(settings, engine, redis, heads)
    assert report["state"] == expected
    assert report["model_requests"] == report["catalog_requests"] == 0
    assert report["read_only"]
    assert "readiness-fixture-key" not in json.dumps(report)
    assert "redis://test" not in json.dumps(report)
    async with engine.connect() as connection:
        assert (await connection.execute(select(AIDailyUsage))).all() == before
    assert sorted([key async for key in redis.scan_iter()]) == keys
    if case == "old_budget":
        assert report["checks"]["budget"]["used"] == 0
    if case == "exhausted":
        assert report["checks"]["budget"]["used"] == 100
