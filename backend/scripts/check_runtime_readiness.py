"""Read-only operator check; no model/catalog request or allowance reservation.

Exit 0 means local prerequisites for uncached work are present, 2 means the known
daily allowance is exhausted (cached-only operation), and 1 means not ready.
This does not establish provider credentials, recommendation quality or public
deployment readiness. The existing health endpoint remains a connectivity check.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy import Column, MetaData, String, Table, select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.cache import make_redis
from app.config import get_settings
from app.daily_budget import DailyBudget
from app.db import make_engine
from app.usage import UsageUnavailable

TIMEOUT_SECONDS = 2
EXPECTED_CAP = 100
VERSION_TABLE = Table(
    "alembic_version", MetaData(), Column("version_num", String(32), primary_key=True)
)


def expected_heads():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    heads = sorted(ScriptDirectory.from_config(config).get_heads())
    if not heads:
        raise ValueError("Migration head is unavailable")
    return heads


async def migration_status(engine, expected):
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS), engine.connect() as connection:
            actual = sorted((await connection.scalars(select(VERSION_TABLE))).all())
        return {
            "status": "ok" if actual == expected else "migration_mismatch",
            "expected_heads": expected,
            "actual_heads": actual,
        }
    except DBAPIError as error:
        missing = getattr(error.orig, "sqlstate", None) == "42P01"
        return {"status": "migration_missing" if missing else "unavailable"}
    except (SQLAlchemyError, OSError, TimeoutError):
        return {"status": "unavailable"}


async def redis_status(redis):
    try:
        async with asyncio.timeout(TIMEOUT_SECONDS):
            return {"status": "ok" if await redis.ping() else "unavailable"}
    except (RedisError, OSError, TimeoutError):
        return {"status": "unavailable"}


async def inspect_runtime(settings, engine, redis, heads, *, expected_cap=EXPECTED_CAP):
    postgres, cache = await asyncio.gather(
        migration_status(engine, heads), redis_status(redis)
    )
    key = settings.openai_api_key
    model = {
        "name_configured": bool(settings.llm_model.strip()),
        "key_configured": bool(key and key.get_secret_value().strip()),
        "remote_credentials_verified": False,
    }
    budget = {"status": "not_checked"}
    if postgres["status"] == "ok":
        try:
            async with asyncio.timeout(TIMEOUT_SECONDS):
                snapshot = await DailyBudget(
                    engine, settings.daily_ai_call_cap
                ).snapshot()
            budget = {
                "status": "available"
                if snapshot["used"] < snapshot["daily_cap"]
                else "exhausted",
                "utc_day": snapshot["utc_day"],
                "used": snapshot["used"],
                "cap": snapshot["daily_cap"],
            }
        except (UsageUnavailable, OSError, TimeoutError):
            budget = {"status": "unknown"}
    issues = []
    if postgres["status"] != "ok":
        issues.append("database_or_migrations_unready")
    if cache["status"] != "ok":
        issues.append("redis_unavailable")
    if settings.daily_ai_call_cap != expected_cap:
        issues.append(f"daily_cap_must_be_{expected_cap}")
    if not all(model[field] for field in ["name_configured", "key_configured"]):
        issues.append("model_configuration_missing")
    if budget["status"] in {"unknown", "not_checked"}:
        issues.append("budget_requires_operator_review")
    state = (
        "not_ready"
        if issues
        else "cached_only"
        if budget["status"] == "exhausted"
        else "ready"
    )
    return {
        "state": state,
        "expected_daily_cap": expected_cap,
        "uncached_model_work_locally_ready": state == "ready",
        "checks": {
            "postgres": postgres,
            "redis": cache,
            "budget": budget,
            "model": model,
        },
        "issues": issues,
        "model_requests": 0,
        "catalog_requests": 0,
        "read_only": True,
        "scope": "Local runtime prerequisites only; no remote provider or public deployment validation",
    }


async def run_check(settings, *, expected_cap=EXPECTED_CAP):
    # Deliberately do not use SQL_ECHO; configuration/connection secrets must not
    # be written into this operator report or SQL logs.
    heads = expected_heads()
    engine = make_engine(settings.database_url)
    redis = None
    try:
        redis = make_redis(settings.redis_url)
        return await inspect_runtime(
            settings, engine, redis, heads, expected_cap=expected_cap
        )
    finally:
        try:
            if redis is not None:
                await redis.aclose()
        finally:
            await engine.dispose()


def main(argv=()):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-daily-cap",
        type=int,
        choices=(100, 200, 300),
        default=EXPECTED_CAP,
        help="Expected configured policy only; 200 or 300 requires an explicitly approved temporary acceptance window. Does not alter usage or configuration.",
    )
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(
            run_check(get_settings(), expected_cap=args.expected_daily_cap)
        )
    except (
        ValidationError,
        SQLAlchemyError,
        ValueError,
        OSError,
        ImportError,
        CommandError,
    ) as error:
        # ValidationError and driver messages can contain credentials/URLs.
        report = {
            "state": "not_ready",
            "issues": ["configuration_or_tooling_unavailable"],
            "error_kind": type(error).__name__,
            "read_only": True,
            "model_requests": 0,
            "catalog_requests": 0,
        }
    print(json.dumps(report, indent=2))
    return {"ready": 0, "not_ready": 1, "cached_only": 2}[report["state"]]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
