"""Verify live book-object persistence in disposable storage, without model calls."""

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import get_settings
from app.daily_budget import DailyBudget
from app.db import make_engine
from app.filters import SearchFilters
from app.graph.parse_query import ParsedQuery
from app.graph.state import SearchState
from app.http_client import make_http_client
from app.models import Base, Book
from app.repository import SearchRepository
from app.sources.google_books import search_google_books
from app.sources.merge import merge_candidates
from app.sources.open_library import search_open_library
from scripts.backup_database import fingerprint


async def verify(report):
    settings = get_settings()
    if urlsplit(settings.database_url).hostname not in {
        "127.0.0.1",
        "localhost",
        "::1",
    }:
        raise ValueError("Use local storage for this disposable diagnostic")
    engine = make_engine(settings.database_url)
    schema = "lumen_test_" + uuid4().hex
    isolated = engine.execution_options(schema_translate_map={None: schema})
    budget = DailyBudget(engine, settings.daily_ai_call_cap)
    created = False
    report.update(
        cases=[],
        model_calls=0,
        source_cache_enabled=False,
        synthetic_storage_input=True,
        daily_ai_call_cap=settings.daily_ai_call_cap,
    )
    try:
        report["daily_before"] = await budget.snapshot()
        async with engine.begin() as connection:
            before = await fingerprint(connection)
            await connection.execute(CreateSchema(schema))
        created = True
        async with isolated.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        repository = SearchRepository(isolated)
        async with make_http_client() as client:

            async def observe(response):
                response.extensions["catalog_fetched_at"] = datetime.now(UTC)

            client.event_hooks["response"].append(observe)
            for language, query in (("en", "magic realism"), ("es", "realismo mágico")):
                case = {"language": language, "sources": [], "stored_candidates": 0}
                report["cases"].append(case)
                results = []
                for provider, call in (
                    (
                        "google_books",
                        partial(
                            search_google_books,
                            client,
                            query,
                            language,
                            settings.google_books_api_key,
                            max_results=5,
                        ),
                    ),
                    (
                        "open_library",
                        partial(search_open_library, client, query, language, limit=5),
                    ),
                ):
                    try:
                        books = await call()
                        case["sources"].append(
                            {
                                "provider": provider,
                                "candidates": len(books),
                                "status": 200,
                            }
                        )
                        results.append(books)
                    except httpx.HTTPError as error:
                        case["sources"].append(
                            {
                                "provider": provider,
                                "error_type": type(error).__name__,
                                "status": error.response.status_code
                                if isinstance(error, httpx.HTTPStatusError)
                                else None,
                            }
                        )
                        results.append([])
                candidates = merge_candidates(*results)
                if not candidates:
                    raise ValueError("No live candidates to verify")
                # Exercise storage with real candidates and explicitly empty
                # picks. This is not a live graph/recommendation quality test.
                state = SearchState(
                    query=query,
                    language=language,
                    filters=SearchFilters(),
                    parsed=ParsedQuery(searches=[query], genre=None),
                    tried=[query],
                    candidates=candidates,
                    retries=2,
                    picks=[],
                )
                await repository.save_completed(uuid4(), state, [], 0)
                for book in candidates:
                    async with isolated.connect() as connection:
                        raw = await connection.scalar(
                            select(Book.raw).where(Book.isbn13 == book.isbn13)
                        )
                    expected = {
                        kind: [v.model_dump(mode="json") for v in values]
                        for kind, values in book.provider_records.items()
                    }
                    assert expected and raw["provider_records"] == expected
                    details = await repository.get_book(book.isbn13)
                    assert details and "provider_records" not in details.model_dump()
                case.update(
                    stored_candidates=len(candidates),
                    original_objects_equal=True,
                    public_details_exclude_originals=True,
                )
        async with engine.begin() as connection:
            after = await fingerprint(connection)
        report["public_tables_unchanged"] = before == after
        report["public_fingerprints"] = after
        report["daily_after"] = await budget.snapshot()
        assert before == after
        assert report["daily_before"]["used"] == report["daily_after"]["used"]
    finally:
        if created:
            assert schema.startswith("lumen_test_") and len(schema) == 43
            async with engine.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            report["temporary_storage_cleaned"] = True
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output
    if output.exists():
        parser.error("Choose a new evidence path")
    root = Path(__file__).resolve().parents[1]
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "complete": False,
        "source_sha256_lf": {
            str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(
                p.read_text("utf-8").encode()
            ).hexdigest()
            for p in [
                *sorted((root / "app/sources").glob("*.py")),
                root / "app/repository.py",
                Path(__file__).resolve(),
            ]
        },
    }
    try:
        asyncio.run(verify(report))
        report["complete"] = True
    except Exception as error:  # noqa: BLE001 - preserve sanitized failure evidence
        report["error_type"] = type(error).__name__
    report["completed_at"] = datetime.now(UTC).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"report": str(output), "complete": report["complete"]}))
    raise SystemExit(0 if report["complete"] else 1)


if __name__ == "__main__":
    main()
