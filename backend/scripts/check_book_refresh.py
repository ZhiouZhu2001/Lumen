"""Verify real catalog refresh using disposable local storage, never aging public books."""

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy import insert, select, text
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.books import router
from app.book_refresh import BookRefresh
from app.cache import JsonCache, make_redis
from app.config import get_settings
from app.db import make_engine
from app.http_client import make_http_client
from app.models import Base, Book
from app.repository import SearchRepository
from app.sources.edition import lookup_edition


class ObservedCache(JsonCache):
    def __init__(self, redis):
        super().__init__(redis)
        self.hits = 0

    async def get(self, key):
        result = await super().get(key)
        self.hits += result is not None
        return result


class GoogleUnavailable(httpx.AsyncBaseTransport):
    """Only this supplementary fallback probe simulates a primary-provider error."""

    def __init__(self):
        self.transport = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        if request.url.host == "www.googleapis.com":
            return httpx.Response(503)
        return await self.transport.handle_async_request(request)

    async def aclose(self):
        await self.transport.aclose()


async def verify(report):
    settings = get_settings()
    for url in (settings.database_url, settings.redis_url):
        if urlsplit(url).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("This diagnostic requires explicitly local storage")
    redis = make_redis(settings.redis_url)
    engine = make_engine(settings.database_url)
    schema = "lumen_test_" + uuid4().hex
    namespace = "lumen:test:" + uuid4().hex
    isolated = engine.execution_options(schema_translate_map={None: schema})
    created = False
    report.update(
        daily_ai_call_cap=settings.daily_ai_call_cap,
        normal_books_aged=False,
        isolated_snapshots_aged_days=31,
        cases=[],
    )
    day = int((await redis.time())[0]) // 86400
    usage_key = f"lumen:usage:v1:ai:{day}"
    report["shared_daily_before"] = int(await redis.get(usage_key) or 0)
    cache = ObservedCache(redis)
    events = []

    async def observe(response):
        events.append(
            {
                "host": response.request.url.host,
                "path": response.request.url.path,
                "status": response.status_code,
            }
        )

    try:
        assert schema.startswith("lumen_test_") and len(schema) == 43
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
        created = True
        async with isolated.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        repository = SearchRepository(isolated)
        public = SearchRepository(engine)
        async with make_http_client(cache=cache) as sources:
            sources.event_hooks["response"].append(observe)
            app = FastAPI()
            app.include_router(router)
            app.state.repository = repository
            app.state.book_refresh = BookRefresh(
                repository,
                sources,
                redis,
                settings.google_books_api_key,
                namespace=namespace + ":refresh",
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as api:
                for isbn, language in [
                    ("9788417346201", "es"),
                    ("9780330483292", "en"),
                ]:
                    before = await public.get_book(isbn)
                    assert before is not None and before.language == language
                    async with engine.connect() as connection:
                        row = (
                            (
                                await connection.execute(
                                    select(Book.__table__).where(Book.isbn13 == isbn)
                                )
                            )
                            .mappings()
                            .one()
                        )
                    values = dict(row)
                    values["fetched_at"] = datetime.now(UTC) - timedelta(days=31)
                    async with isolated.begin() as connection:
                        await connection.execute(insert(Book).values(**values))
                    event_start, hit_start = len(events), cache.hits
                    response = await api.get("/api/books/" + isbn)
                    response.raise_for_status()
                    book = response.json()
                    assert book["isbn13"] == isbn and book["language"] == language
                    assert (
                        datetime.fromisoformat(book["fetched_at"])
                        > values["fetched_at"]
                    )
                    assert not {
                        "reason",
                        "rank",
                        "query",
                        "search_id",
                        "raw",
                    }.intersection(book)
                    persisted = await repository.get_book(isbn)
                    assert persisted.model_dump(mode="json") == book
                    event_end = len(events)
                    again = await api.get("/api/books/" + isbn)
                    assert again.json() == book and len(events) == event_end
                    assert await public.get_book(isbn) == before
                    report["cases"].append(
                        {
                            "isbn13": isbn,
                            "language": language,
                            "http_status": response.status_code,
                            "title": book["title"],
                            "source": book["source"],
                            "before_fetched_at": values["fetched_at"].isoformat(),
                            "after_fetched_at": book["fetched_at"],
                            "persisted_matches_api": True,
                            "second_read_no_provider_calls": True,
                            "public_snapshot_unchanged": True,
                            "private_fields_absent": True,
                            "catalog_cache_hits": cache.hits - hit_start,
                            "client_response_events": events[event_start:event_end],
                        }
                    )
        # Genuine Open Library traffic and normal redirect handling, with only
        # Google Books' failure simulated. This is not a real Google outage.
        async with make_http_client(transport=GoogleUnavailable()) as sources:
            async with asyncio.timeout(3):
                fallback = await lookup_edition(sources, "9780141439518", "en")
            assert fallback is not None and fallback.source == "open_library"
            report["fallback_probe"] = {
                "google_error_simulated": True,
                "open_library_live": True,
                "isbn13": fallback.isbn13,
                "language": fallback.language,
                "source": fallback.source,
                "title": fallback.title,
                "database_writes": False,
            }
        async with isolated.connect() as connection:
            for table in ("searches", "search_results"):
                assert (
                    await connection.scalar(
                        text(f"SELECT count(*) FROM {schema}.{table}")
                    )
                    == 0
                )
        report["search_history_rows_added"] = 0
        report["shared_daily_after"] = int(await redis.get(usage_key) or 0)
        assert report["shared_daily_before"] == report["shared_daily_after"]
    finally:
        if created:
            assert schema.startswith("lumen_test_") and len(schema) == 43
            async with engine.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
        keys = [key async for key in redis.scan_iter(namespace + ":*")]
        if keys:
            assert all(key.startswith(namespace + ":") for key in keys)
            await redis.delete(*keys)
        await redis.aclose()
        await engine.dispose()
        report["temporary_storage_cleaned"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    if output.exists():
        parser.error("Use a new report path; existing evidence is never overwritten")
    root = Path(__file__).resolve().parents[1]
    report = {"started_at": datetime.now(UTC).isoformat(), "complete": False}
    report["source_sha256_lf"] = {
        str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
            path.read_text("utf-8").encode()
        ).hexdigest()
        for path in [
            root / "app/api/books.py",
            root / "app/main.py",
            root / "app/repository.py",
            root / "app/book_refresh.py",
            root / "app/sources/edition.py",
            Path(__file__).resolve(),
        ]
    }
    try:
        asyncio.run(verify(report))
        report["complete"] = True
    except Exception as error:  # noqa: BLE001 - retain sanitized failed-check evidence
        report["error_type"] = type(error).__name__
    report["completed_at"] = datetime.now(UTC).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"report": str(output), "complete": report["complete"]}))
    raise SystemExit(0 if report["complete"] else 1)


if __name__ == "__main__":
    main()
