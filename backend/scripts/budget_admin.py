"""Explicit usage initialization/floor correction while all AI workers are stopped."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.cache import make_redis
from app.config import get_settings
from app.daily_budget import DailyBudget
from app.db import make_engine


async def administer(args):
    settings = get_settings()
    engine = make_engine(settings.database_url)
    redis = make_redis(settings.redis_url)
    budget = DailyBudget(engine, settings.daily_ai_call_cap)
    try:
        async with engine.connect() as connection:
            day, _ = await budget._clock(connection)
        report = {
            "mode": args.mode,
            "utc_day": day.isoformat(),
            "daily_cap": settings.daily_ai_call_cap,
            "ai_workers_stopped_acknowledged": True,
        }
        if args.mode in {"import-redis", "export-redis-floor"}:
            seconds, _ = await redis.time()
            if datetime.fromtimestamp(seconds, UTC).date() != day:
                raise ValueError("Redis and PostgreSQL UTC dates disagree")
            key = f"lumen:usage:v1:ai:{seconds // 86400}"
            value = await redis.get(key)
            if args.mode == "export-redis-floor":
                status = await budget.snapshot()
                if status["utc_day"] != day.isoformat():
                    raise ValueError(
                        "UTC day changed; retry while workers remain stopped"
                    )
                script = """
local floor = tonumber(ARGV[1])
local value = redis.call('GET', KEYS[1])
local current = tonumber(value or '0')
if not current or current < 0 then return redis.error_reply('Invalid legacy count') end
local used = math.max(current, floor)
redis.call('SET', KEYS[1], used, 'EX', ARGV[2])
return used
"""
                stored = await redis.eval(
                    script, 1, key, status["used"], status["retry_after"]
                )
                report.update(
                    requested_floor=status["used"],
                    stored_used=stored,
                    legacy_keys_cleared=False,
                )
                return report
            # A missing counter is not evidence of zero requests after data loss.
            used = int(value) if value is not None else settings.daily_ai_call_cap
            report["legacy_counter_present"] = value is not None
        elif args.mode == "block-today":
            used = settings.daily_ai_call_cap
        else:
            if args.used is None:
                raise ValueError(
                    "initialize requires an explicitly verified --used value"
                )
            used = args.used
        report["requested_floor"] = used
        report["stored_used"] = await budget.raise_floor(used, expected_day=day)
        report["legacy_keys_cleared"] = False
        return report
    finally:
        await redis.aclose()
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=["import-redis", "initialize", "block-today", "export-redis-floor"],
    )
    parser.add_argument("--used", type=int)
    parser.add_argument(
        "--confirm-ai-workers-stopped", action="store_true", required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new receipt path; existing evidence is never overwritten")
    result = asyncio.run(administer(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
