import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.book_refresh import MAX_AGE, BookRefresh
from app.channels.schemas import BookDetails
from app.repository import StorageUnavailable
from app.sources.edition import lookup_edition, parse_open_library_edition
from tests.persistence_fixtures import completed

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def saved(age=31):
    _, cards = completed(1)
    return BookDetails(
        **cards[0].model_dump(exclude={"rank", "reason"}),
        fetched_at=NOW - timedelta(days=age),
    )


def service(redis=None):
    repository = AsyncMock()
    redis = redis or AsyncMock()
    redis.set.return_value = True
    return BookRefresh(repository, object(), redis, now=lambda: NOW)


@pytest.mark.parametrize("age", [0, 29, -1])
async def test_fresh_or_future_snapshots_do_not_use_redis_or_sources(age):
    refresh = service()
    book = saved(age)
    assert await refresh.refresh(book) is book
    refresh.redis.set.assert_not_awaited()
    refresh.repository.refresh_book.assert_not_awaited()


async def test_exact_30_day_boundary_refreshes_and_uses_separate_expiring_lease():
    refresh = service()
    book = saved(30)
    newer = saved(0)
    refresh.repository.refresh_book.return_value = newer
    with patch(
        "app.book_refresh.lookup_edition", AsyncMock(return_value=newer)
    ) as lookup:
        assert await refresh.refresh(book) is newer
        assert NOW - book.fetched_at == MAX_AGE
        lookup.assert_awaited_once_with(
            refresh.client, book.isbn13, book.language, None
        )
    refresh.redis.set.assert_awaited_once_with(
        f"lumen:refresh:v1:{book.isbn13}", "1", nx=True, ex=300
    )
    refresh.repository.refresh_book.assert_awaited_once_with(book, newer)


async def test_existing_attempt_lease_prevents_duplicate_provider_work():
    refresh = service()
    refresh.redis.set.return_value = False
    book = saved()
    with patch("app.book_refresh.lookup_edition", AsyncMock()) as lookup:
        assert await refresh.refresh(book) is book
        lookup.assert_not_awaited()


@pytest.mark.parametrize("failure", [RedisConnectionError(), TimeoutError()])
async def test_unavailable_lease_keeps_old_snapshot_without_provider_calls(failure):
    refresh = service()
    refresh.redis.set.side_effect = failure
    book = saved()
    with patch("app.book_refresh.lookup_edition", AsyncMock()) as lookup:
        assert await refresh.refresh(book) is book
        lookup.assert_not_awaited()


@pytest.mark.parametrize(
    "failure", [StorageUnavailable("private URL"), ValueError(), TimeoutError()]
)
async def test_optional_refresh_failure_never_advances_the_returned_snapshot(failure):
    refresh = service()
    book = saved()
    refresh.repository.refresh_book.side_effect = failure
    with patch("app.book_refresh.lookup_edition", AsyncMock(return_value=saved(0))):
        assert await refresh.refresh(book) is book
    assert book.fetched_at == NOW - timedelta(days=31)


async def test_no_exact_edition_does_not_write_and_busy_worker_does_not_queue():
    refresh = service()
    book = saved()
    with patch(
        "app.book_refresh.lookup_edition", AsyncMock(return_value=None)
    ) as lookup:
        assert await refresh.refresh(book) is book
        refresh.repository.refresh_book.assert_not_awaited()
        for _ in range(3):
            await refresh.slots.acquire()
        try:
            assert await refresh.refresh(book) is book
            assert lookup.await_count == 1
        finally:
            for _ in range(3):
                refresh.slots.release()


async def test_cancellation_propagates_instead_of_starting_background_work():
    refresh = service()
    entered = asyncio.Event()

    async def pause(*args):
        entered.set()
        await asyncio.Event().wait()

    with patch("app.book_refresh.lookup_edition", pause):
        task = asyncio.create_task(refresh.refresh(saved()))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert not refresh.slots.locked()
    refresh.repository.refresh_book.assert_not_awaited()


async def test_overall_deadline_cancels_slow_sources_and_returns_the_old_snapshot():
    refresh = service()
    book = saved()
    cancelled = asyncio.Event()

    async def pause(*args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    with (
        patch("app.book_refresh.REFRESH_TIMEOUT_SECONDS", 0.01),
        patch("app.book_refresh.lookup_edition", pause),
    ):
        assert await refresh.refresh(book) is book
    assert cancelled.is_set()
    refresh.repository.refresh_book.assert_not_awaited()


def edition(isbn13, language="spa", **extra):
    return {
        "isbn_13": [isbn13],
        "title": "Exact saved edition",
        "languages": [{"key": f"/languages/{language}"}],
        "publish_date": "July 3, 2018",
        "number_of_pages": 128,
        "authors": [{"key": "/authors/OL1A"}],
        **extra,
    }


@pytest.mark.parametrize(
    "defect", ["isbn", "language", "missing_language", "title", "pages"]
)
def test_edition_requires_its_own_isbn_language_and_valid_metadata(defect):
    book = saved()
    data = edition(book.isbn13)
    if defect == "isbn":
        data["isbn_13"] = ["9780141439518"]
    if defect == "language":
        data["languages"] = [{"key": "/languages/eng"}]
    if defect == "missing_language":
        data.pop("languages")
    if defect == "title":
        data["title"] = ""
    if defect == "pages":
        data["number_of_pages"] = -1
    assert parse_open_library_edition(data, book.isbn13, "es") is None


def test_edition_does_not_turn_author_ids_into_names_or_use_work_metadata():
    book = saved()
    result = parse_open_library_edition(
        edition(book.isbn13, covers=[-1, 123], description={"value": "Original text"}),
        book.isbn13,
        "es",
    )
    assert result.authors == [] and result.published_year == 2018
    assert result.cover_url == "https://covers.openlibrary.org/b/id/123-M.jpg"
    assert result.description == "Original text" and result.rating is None


@pytest.mark.parametrize("google_failed", [False, True])
async def test_lookup_is_bounded_exact_and_can_fall_back_to_matching_edition(
    google_failed,
):
    book = saved()
    calls = []
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/google_books_real_es.json").read_text(
            "utf-8"
        )
    )

    def respond(request):
        calls.append(request)
        assert request.extensions["timeout"]["read"] == 2
        if request.url.host == "www.googleapis.com":
            assert request.url.params["q"] == f"isbn:{book.isbn13}"
            assert request.headers["X-Goog-Api-Key"] == "test-only-key"
            return httpx.Response(503 if google_failed else 200, json=fixture)
        assert request.url == f"https://openlibrary.org/isbn/{book.isbn13}.json"
        return httpx.Response(200, json=edition(book.isbn13))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await lookup_edition(client, book.isbn13, "es", "test-only-key")
    assert len(calls) == 2 and result.isbn13 == book.isbn13 and result.language == "es"
    assert result.source == ("open_library" if google_failed else "google_books")
    assert result.catalog_fetched_at.tzinfo is not None


async def test_other_editions_and_unavailable_sources_do_not_become_new_books():
    book = saved()

    def respond(request):
        if request.url.host == "www.googleapis.com":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(200, json=edition("9780141439518"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await lookup_edition(client, book.isbn13, "es") is None
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(503))
    ) as client:
        assert await lookup_edition(client, book.isbn13, "es") is None


@pytest.mark.parametrize(
    "location,expected_requests",
    [
        ("https://openlibrary.org/books/OL123M.json", 3),
        ("/books/OL123M.json", 3),
        ("https://evil.test/books/OL123M.json", 2),
        ("http://openlibrary.org/books/OL123M.json", 2),
        ("https://openlibrary.org/works/OL123W.json", 2),
        ("https://user:password@openlibrary.org/books/OL123M.json", 2),
    ],
)
async def test_open_library_redirect_is_single_hop_and_only_to_its_edition_api(
    location, expected_requests
):
    book = saved()
    calls = []

    def respond(request):
        calls.append(request.url)
        if request.url.host == "www.googleapis.com":
            return httpx.Response(503)
        if request.url.path.startswith("/isbn/"):
            return httpx.Response(302, headers={"location": location})
        return httpx.Response(200, json=edition(book.isbn13))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await lookup_edition(client, book.isbn13, "es")
    assert len(calls) == expected_requests
    assert (result is not None) is (expected_requests == 3)
