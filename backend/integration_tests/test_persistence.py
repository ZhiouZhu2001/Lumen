from copy import deepcopy
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from app.api.books import router as books_router
from app.models import Book, Search, SearchResult
from app.repository import StorageUnavailable
from tests.persistence_fixtures import completed


async def counts(engine):
    async with engine.connect() as c:
        return [
            (await c.execute(select(func.count()).select_from(model))).scalar_one()
            for model in (Book, Search, SearchResult)
        ]


async def test_concurrent_searches_share_books_without_losing_results(storage):
    import asyncio

    repository, engine = storage
    first, cards = completed(2)
    second, other = deepcopy(first), deepcopy(cards)
    other.reverse()
    second["picks"].reverse()
    for rank, (card, pick) in enumerate(zip(other, second["picks"], strict=True), 1):
        card.rank = pick.rank = rank
        card.reason = pick.reason = (
            "Otra lectura del catálogo. Puedes consultar sus detalles."
        )
    await asyncio.wait_for(
        asyncio.gather(
            repository.save_completed(uuid4(), first, cards, 100),
            repository.save_completed(uuid4(), second, other, 150),
        ),
        timeout=10,
    )
    assert await counts(engine) == [2, 2, 4]


async def test_cancelling_an_inflight_transaction_rolls_back_its_book_rows(storage):
    import asyncio

    from sqlalchemy import event

    repository, engine = storage
    state, cards = completed(1)
    entered = asyncio.Event()

    def pause(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("INSERT INTO") and ".searches " in statement:
            entered.set()
            cursor.execute("SELECT pg_sleep(10)")

    event.listen(engine.sync_engine, "before_cursor_execute", pause)
    task = asyncio.create_task(repository.save_completed(uuid4(), state, cards, 100))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        event.remove(engine.sync_engine, "before_cursor_execute", pause)
    assert await counts(engine) == [0, 0, 0]


async def test_completed_search_is_atomic_traceable_and_private(storage):
    repository, engine = storage
    state, cards = completed()
    search_id = uuid4()
    await repository.save_completed(search_id, state, cards, 250)
    assert await counts(engine) == [2, 1, 2]
    async with engine.connect() as c:
        stored = (await c.execute(select(Search.__table__))).mappings().one()
        assert stored["query_text"] == state["query"] and stored[
            "candidate_count"
        ] == len(state["candidates"])
        assert (
            stored["duration_ms"] == 250
            and stored["parsed_query"]["searches"] == state["parsed"].searches
        )
        rows = (
            (
                await c.execute(
                    select(SearchResult.__table__).order_by(SearchResult.rank)
                )
            )
            .mappings()
            .all()
        )
        assert [(r["isbn13"], r["reason"]) for r in rows] == [
            (b.isbn13, b.reason) for b in cards
        ]
        raw = (await c.execute(select(Book.raw))).scalars().all()
        assert all(
            set(value) == {"snapshot_version", "source", "links"} for value in raw
        )
        assert not any(key in stored for key in ("ip", "user_agent", "client"))
    detail = await repository.get_book(cards[0].isbn13)
    assert detail.title == cards[0].title and detail.source == cards[0].source
    assert detail.fetched_at.tzinfo is not None
    assert not {"reason", "rank", "query", "search_id", "work_key"}.intersection(
        detail.model_dump()
    )


async def test_zero_results_stores_the_search_without_fabricating_books(storage):
    repository, engine = storage
    state, cards = completed(0)
    await repository.save_completed(uuid4(), state, cards, 100)
    assert await counts(engine) == [0, 1, 0]


async def test_duplicate_search_failure_rolls_back_book_updates_and_new_rows(storage):
    repository, engine = storage
    state, cards = completed(1)
    search_id = uuid4()
    await repository.save_completed(search_id, state, cards, 100)
    newer, new_cards = completed(2)
    newer["candidates"][0].title = "Changed title"
    new_cards[0].title = "Changed title"
    with pytest.raises(StorageUnavailable):
        await repository.save_completed(search_id, newer, new_cards, 150)
    assert await counts(engine) == [1, 1, 1]
    assert (await repository.get_book(cards[0].isbn13)).title == cards[0].title
    assert await repository.get_book(new_cards[1].isbn13) is None


async def test_book_refresh_preserves_missing_metadata_and_keeps_search_reasons_separate(
    storage,
):
    repository, engine = storage
    state, cards = completed(1)
    from decimal import Decimal

    from app.sources.schemas import Rating

    rating = Rating(value=Decimal("4.2"), count=10, source="Google Books")
    state["candidates"][0].rating = rating
    state["candidates"][0].page_count = 123
    cards[0].rating = rating
    cards[0].page_count = 123
    await repository.save_completed(uuid4(), state, cards, 100)
    later = deepcopy(state)
    revised = deepcopy(cards)
    later["candidates"][0].rating = None
    later["candidates"][0].page_count = None
    revised[0].rating = None
    revised[0].page_count = None
    later["picks"][0].reason = revised[0].reason = (
        "Otra lectura del catálogo. Puedes conocer sus detalles."
    )
    await repository.save_completed(uuid4(), later, revised, 200)
    assert await counts(engine) == [1, 2, 2]
    details = await repository.get_book(cards[0].isbn13)
    assert details.rating == rating and details.page_count == 123
    assert "reason" not in details.model_dump()


async def test_an_isbn_cannot_silently_change_language(storage):
    repository, engine = storage
    state, cards = completed(1)
    await repository.save_completed(uuid4(), state, cards, 100)
    other = deepcopy(state)
    revised = deepcopy(cards)
    other["language"] = "en"
    for book in other["candidates"]:
        book.language = "en"
    revised[0].language = "en"
    with pytest.raises(StorageUnavailable, match="Conflicting catalog language"):
        await repository.save_completed(uuid4(), other, revised, 100)
    assert await counts(engine) == [1, 1, 1]
    assert (await repository.get_book(cards[0].isbn13)).language == "es"


@pytest.mark.parametrize(
    "defect",
    [
        "unknown",
        "partial",
        "rank",
        "metadata",
        "reason",
        "filter",
        "unfinished",
        "nonsense_picks",
        "noncanonical",
    ],
)
async def test_invalid_snapshots_never_write_rows(storage, defect):
    repository, engine = storage
    state, cards = completed(2)
    if defect == "unknown":
        cards[0].isbn13 = "9780141439518"
    elif defect == "partial":
        cards.pop()
    elif defect == "rank":
        cards[0].rank = 2
    elif defect == "metadata":
        cards[0].title = "Invented title"
    elif defect == "reason":
        cards[0].reason = "Changed explanation"
    elif defect == "unfinished":
        state["retries"] = 0
    elif defect == "nonsense_picks":
        state["parsed"].is_book_request = False
    elif defect == "noncanonical":
        cards[0].isbn13 = state["picks"][0].isbn13 = " " + cards[0].isbn13 + " "
    else:
        from app.filters import SearchFilters

        state["filters"] = SearchFilters(era="2020s")
        state["candidates"][0].published_year = cards[0].published_year = 1990
    with pytest.raises(ValueError):
        await repository.save_completed(uuid4(), state, cards, 100)
    assert await counts(engine) == [0, 0, 0]


async def test_database_foreign_key_rejects_an_unknown_book(storage):
    repository, engine = storage
    state, cards = completed(0)
    search_id = uuid4()
    await repository.save_completed(search_id, state, cards, 100)
    with pytest.raises(IntegrityError):
        async with engine.begin() as c:
            await c.execute(
                insert(SearchResult).values(
                    search_id=search_id,
                    isbn13="9780141439518",
                    rank=1,
                    reason="Not retrieved",
                )
            )
    assert await counts(engine) == [0, 1, 0]


async def test_details_regenerate_safe_current_channels_and_ignore_legacy_or_unsafe_links(
    storage,
):
    repository, engine = storage
    state, cards = completed(1)
    await repository.save_completed(uuid4(), state, cards, 100)
    raw = {
        "snapshot_version": 1,
        "source": "google_books",
        "links": [
            {
                "store": "apple_books",
                "label": "Unsafe",
                "url": "https://evil.test/book",
                "formats": ["apple_books"],
                "match": "title_author",
            },
            {
                "store": "gutenberg",
                "label": "Retired",
                "url": "https://www.gutenberg.org/ebooks/1342",
                "formats": ["free"],
                "match": "title_author",
            },
            {
                "store": "apple_books",
                "label": "Old label",
                "url": "https://books.apple.com/es/book/example/id123",
                "formats": ["free"],
                "match": "title_author",
            },
        ],
    }
    from sqlalchemy import update

    async with engine.begin() as c:
        await c.execute(update(Book).values(raw=raw, formats=["free"]))
    details = await repository.get_book(cards[0].isbn13)
    assert {l.store for l in details.links} == {
        "amazon_es",
        "casa_del_libro",
        "abacus",
        "apple_books",
    }
    apple = next(l for l in details.links if l.store == "apple_books")
    assert (
        apple.label == "Apple Books"
        and apple.formats == ["apple_books"]
        and not apple.language_verified
    )
    assert "free" not in details.formats
    async with engine.begin() as c:
        await c.execute(
            update(Book).values(
                raw={"old_format": True, "source": "private://legacy-connection"}
            )
        )
    assert (await repository.get_book(cards[0].isbn13)).source == "catalog_cache"


async def test_http_details_return_saved_metadata_without_search_private_fields(
    storage,
):
    repository, _ = storage
    state, cards = completed(1)
    await repository.save_completed(uuid4(), state, cards, 100)
    app = FastAPI()
    app.state.repository = repository
    app.include_router(books_router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/books/" + cards[0].isbn13)
        missing = await client.get("/api/books/9780141439518")
        malformed = await client.get("/api/books/9780141439519")
    assert response.status_code == 200 and response.json()["isbn13"] == cards[0].isbn13
    assert "reason" not in response.json() and "search_id" not in response.json()
    assert missing.status_code == 404 and malformed.status_code == 422
