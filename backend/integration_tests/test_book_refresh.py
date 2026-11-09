import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, update

from app.api.books import router
from app.book_refresh import BookRefresh
from app.channels.schemas import BookLink
from app.models import Book, Search, SearchResult
from app.sources.schemas import BookCandidate, Rating
from tests.persistence_fixtures import completed


async def seed(storage):
    repository, engine = storage
    state, cards = completed(1)
    state["candidates"] = state["candidates"][:1]
    await repository.save_completed(uuid4(), state, cards, 100)
    async with engine.begin() as connection:
        await connection.execute(
            update(Book).values(fetched_at=datetime.now(UTC) - timedelta(days=31))
        )
    return await repository.get_book(cards[0].isbn13)


def candidate(book, **changes):
    return BookCandidate.model_validate(
        {
            **book.model_dump(exclude={"links", "formats", "fetched_at"}),
            "catalog_fetched_at": datetime.now(UTC) - timedelta(seconds=1),
            **changes,
        }
    )


async def counts(engine):
    async with engine.connect() as connection:
        return [
            await connection.scalar(select(func.count()).select_from(model))
            for model in (Book, Search, SearchResult)
        ]


async def test_refresh_only_updates_existing_book_and_preserves_history_and_optionals(
    storage,
):
    repository, engine = storage
    original = await seed(storage)
    rating = Rating(value=Decimal("4.2"), count=10, source="Google Books")
    async with engine.begin() as connection:
        await connection.execute(
            update(Book).values(
                rating_value=rating.value,
                rating_count=10,
                rating_source=rating.source,
                page_count=123,
            )
        )
    original = await repository.get_book(original.isbn13)
    async with engine.connect() as connection:
        old_reason = await connection.scalar(select(SearchResult.reason))
    incoming = candidate(
        original,
        title="Updated recorded edition",
        authors=[],
        description=None,
        page_count=None,
        rating=None,
        genres=[],
    )
    result = await repository.refresh_book(original, incoming)
    assert (
        result.title == incoming.title
        and result.fetched_at == incoming.catalog_fetched_at
    )
    assert (
        result.authors == original.authors
        and result.description == original.description
    )
    assert result.rating == rating and result.page_count == 123
    assert result.genres == original.genres
    assert await counts(engine) == [1, 1, 1]
    async with engine.connect() as connection:
        assert await connection.scalar(select(SearchResult.reason)) == old_reason
        raw = await connection.scalar(select(Book.raw))
    assert set(raw) == {"snapshot_version", "source", "links", "provider_records"}
    assert not {"query", "reason", "rank", "search_id"}.intersection(
        result.model_dump()
    )


@pytest.mark.parametrize(
    "defect",
    ["isbn", "language", "source", "missing_time", "old_time", "future_time", "title"],
)
async def test_invalid_refresh_cannot_mutate_books_or_timestamps(storage, defect):
    repository, engine = storage
    original = await seed(storage)
    incoming = candidate(original)
    if defect == "isbn":
        incoming.isbn13 = "9780141439518"
    if defect == "language":
        incoming.language = "en"
    if defect == "source":
        incoming.source = "unverified"
    if defect == "missing_time":
        incoming.catalog_fetched_at = None
    if defect == "old_time":
        incoming.catalog_fetched_at = original.fetched_at
    if defect == "future_time":
        incoming.catalog_fetched_at = datetime.now(UTC) + timedelta(days=1)
    if defect == "title":
        incoming.title = "   "
    with pytest.raises(ValueError):
        await repository.refresh_book(original, incoming)
    assert await repository.get_book(original.isbn13) == original
    assert await counts(engine) == [1, 1, 1]


async def test_delayed_refresh_does_not_overwrite_a_concurrent_newer_snapshot(storage):
    repository, engine = storage
    original = await seed(storage)
    first = candidate(
        original,
        title="Newer stored catalog",
        catalog_fetched_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    delayed = candidate(
        original,
        title="Older delayed catalog",
        catalog_fetched_at=datetime.now(UTC) - timedelta(hours=1),
    )
    assert (await repository.refresh_book(original, first)).title == first.title
    result = await repository.refresh_book(original, delayed)
    assert result.title == first.title and result.fetched_at == first.catalog_fetched_at
    assert await counts(engine) == [1, 1, 1]


async def test_refresh_never_inserts_an_unsaved_book(storage):
    from app.channels.schemas import BookDetails

    _, cards = completed(1)
    original = BookDetails(
        **cards[0].model_dump(exclude={"rank", "reason"}),
        fetched_at=datetime.now(UTC) - timedelta(days=31),
    )
    repository, engine = storage
    assert await repository.refresh_book(original, candidate(original)) is None
    assert await counts(engine) == [0, 0, 0]


@pytest.mark.parametrize("change_identity", [False, True])
async def test_optional_apple_match_is_retained_only_for_unchanged_identity(
    storage, change_identity
):
    repository, engine = storage
    original = await seed(storage)
    link = BookLink(
        store="apple_books",
        label="Apple Books",
        url="https://books.apple.com/es/book/example/id123",
        formats=["apple_books"],
        match="title_author",
    )
    async with engine.begin() as connection:
        raw = await connection.scalar(select(Book.raw))
        raw["links"].append(link.model_dump(mode="json"))
        await connection.execute(update(Book).values(raw=raw))
    original = await repository.get_book(original.isbn13)
    incoming = candidate(
        original,
        title="Changed catalog identity" if change_identity else original.title,
    )
    result = await repository.refresh_book(original, incoming)
    assert (
        any(link.store == "apple_books" for link in result.links) is not change_identity
    )


async def test_two_workers_share_redis_attempt_lease_and_api_returns_real_updated_storage(
    storage, redis_scope
):
    repository, engine = storage
    redis, prefix = redis_scope
    original = await seed(storage)
    calls = []

    async def respond(request):
        calls.append(request.url.host)
        await asyncio.sleep(0.03)
        if request.url.host == "www.googleapis.com":
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "isbn_13": [original.isbn13],
                "languages": [{"key": "/languages/spa"}],
                "title": "Exact refreshed edition",
                "number_of_pages": 200,
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as source_client:
        workers = [
            BookRefresh(repository, source_client, redis, namespace=prefix + ":refresh")
            for _ in range(2)
        ]
        results = await asyncio.gather(
            *(worker.refresh(original) for worker in workers)
        )
        assert (
            len(calls) == 2
            and sum(b.title == "Exact refreshed edition" for b in results) == 1
        )
        assert 0 < await redis.ttl(prefix + ":refresh:" + original.isbn13) <= 300
        app = FastAPI()
        app.include_router(router)
        app.state.repository = repository
        app.state.book_refresh = workers[0]
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/books/" + original.isbn13)
        assert (
            response.status_code == 200
            and response.json()["title"] == "Exact refreshed edition"
        )
        assert len(calls) == 2
        assert await counts(engine) == [1, 1, 1]


async def test_failed_live_boundary_keeps_stale_storage_and_cooldown(
    storage, redis_scope
):
    repository, engine = storage
    redis, prefix = redis_scope
    original = await seed(storage)
    calls = []

    def unavailable(request):
        calls.append(request.url.host)
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable)) as client:
        refresh = BookRefresh(repository, client, redis, namespace=prefix + ":refresh")
        assert await refresh.refresh(original) == original
        assert await refresh.refresh(original) == original
    assert len(calls) == 2
    assert await repository.get_book(original.isbn13) == original
    assert await counts(engine) == [1, 1, 1]
