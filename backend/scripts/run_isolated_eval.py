"""Isolate evaluation cache/hour keys while charging the real shared AI budget.

Copies existing real cache values with their TTLs; never copies or clears IP
counters. Production usage implementation remains active for both policies.
"""

import argparse
import asyncio
import ctypes
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import app.main as application
from app.cache import JsonCache, make_redis
from app.config import get_settings
from app.filters import SearchFilters, constrained_query
from app.search_cache import SearchCache
from app.usage import UsageGuards
from evals.checks import load_suite
from evals.http_run import run_http_live


class EvaluationUsage:
    def __init__(self, hourly_redis, shared_redis, cap):
        self.hourly = UsageGuards(hourly_redis, cap)
        self.daily = UsageGuards(shared_redis, cap)

    async def admit_search(self, address):
        await self.hourly.admit_search(address)

    async def check_daily(self):
        await self.daily.check_daily()

    async def consume_ai(self):
        await self.daily.consume_ai()


@contextmanager
def active_execution():
    """Inhibit idle system sleep only for this Windows process's active run."""
    previous = 0
    function = None
    if os.name == "nt":
        function = ctypes.windll.kernel32.SetThreadExecutionState
        function.argtypes = [ctypes.c_uint32]
        function.restype = ctypes.c_uint32
        previous = function(0x80000001)
    try:
        yield bool(previous)
    finally:
        if previous:
            function(previous)


async def run(args, execution_request):
    assert not args.output.exists() and not args.environment.exists()
    original = get_settings()
    source_parts = urlsplit(original.redis_url)
    assert str(args.redis_db) != source_parts.path.lstrip("/")
    target_url = urlunsplit(source_parts._replace(path="/" + str(args.redis_db)))
    shared, isolated = make_redis(original.redis_url), make_redis(target_url)
    old_environment = os.environ.get("REDIS_URL")
    old_factory = application.UsageGuards
    metadata = None
    try:
        assert await isolated.dbsize() == 0, "Select an empty dedicated test database"
        now, _ = await shared.time()
        day = now // 86400
        used = int(await shared.get(f"lumen:usage:v1:ai:{day}") or 0)
        assert used < original.daily_ai_call_cap
        cache = SearchCache(JsonCache(shared), original.llm_model)
        copied = 0
        for prefix in (f"lumen:cache:v1:{cache.version}:", "lumen:catalog:v2:"):
            async for key in shared.scan_iter(match=prefix + "*"):
                assert key.startswith(prefix)
                copied += int(
                    await shared.execute_command("COPY", key, key, "DB", args.redis_db)
                )
        cases = load_suite(Path("evals/queries.yaml")).cases
        hits = {"result": 0, "parse": 0}
        for case in cases:
            filters = SearchFilters.model_validate(case.filters.model_dump())
            hits["result"] += bool(
                await isolated.exists(
                    cache.result_key(case.query, case.language, filters)
                )
            )
            hits["parse"] += bool(
                await isolated.exists(
                    cache.key(
                        "parse", [constrained_query(case.query, filters), case.language]
                    )
                )
            )
        os.environ["REDIS_URL"] = target_url
        get_settings.cache_clear()
        application.UsageGuards = lambda redis, cap: EvaluationUsage(redis, shared, cap)
        config = Path(__file__).resolve().parents[2] / "frontend/next.config.ts"
        metadata = {
            "started_at": datetime.now(UTC).isoformat(),
            "complete": False,
            "daily_ai_call_cap": original.daily_ai_call_cap,
            "shared_daily_before": used,
            "shared_daily_database": source_parts.path,
            "cache_and_hourly_database": args.redis_db,
            "hourly_limit": 20,
            "policy_implementation": "Unchanged UsageGuards methods; hourly admission uses isolated Redis, actual model attempts use the normal shared Redis counter.",
            "counters_cleared": False,
            "budget_increased": False,
            "real_cache_keys_copied_with_ttl": copied,
            "initial_cache_hits": hits,
            "cache_signature": cache.version,
            "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "frontend_config_sha256": hashlib.sha256(config.read_bytes()).hexdigest(),
            "temporary_idle_sleep_inhibition": execution_request,
            "cache_note": "These are valid cached API/graph results under unchanged backend source; this retry is not described as a fully cold run.",
        }
        args.environment.write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"Shared daily budget {used}/{original.daily_ai_call_cap}; active isolated hourly limit 20; cache hits {hits}",
            flush=True,
        )
        code = await run_http_live(
            Path("evals/queries.yaml"),
            args.output,
            60,
            frontend_url=args.frontend,
            backend_port=args.backend_port,
        )
        after, _ = await shared.time()
        assert after // 86400 == day
        count = int(await shared.get(f"lumen:usage:v1:ai:{day}") or 0)
        metadata.update(
            complete=True,
            completed_at=datetime.now(UTC).isoformat(),
            shared_daily_after=count,
            remaining_attempts=max(0, original.daily_ai_call_cap - count),
            exit_code=code,
            report_sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
        )
        args.environment.write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"Shared daily budget after run {count}/{original.daily_ai_call_cap}",
            flush=True,
        )
        return code
    finally:
        application.UsageGuards = old_factory
        if old_environment is None:
            os.environ.pop("REDIS_URL", None)
        else:
            os.environ["REDIS_URL"] = old_environment
        get_settings.cache_clear()
        await isolated.aclose()
        await shared.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-db", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--frontend", default="http://127.0.0.1:3000")
    parser.add_argument("--backend-port", type=int, default=8001)
    args = parser.parse_args()
    url = urlsplit(args.frontend)
    if (
        not 1 <= args.redis_db <= 15
        or not 0 < args.backend_port < 65536
        or url.scheme != "http"
        or url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        parser.error("Select a dedicated Redis database and loopback HTTP target")
    with active_execution() as enabled:
        return asyncio.run(run(args, enabled))


if __name__ == "__main__":
    raise SystemExit(main())
