import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.sources.open_library import (
    FIELDS,
    OPEN_LIBRARY_URL,
    parse_open_library,
    search_open_library,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def spanish_books():
    return parse_open_library(load("open_library_edge_cases.json"), "es")


def test_keeps_only_usable_spanish_books(spanish_books) -> None:
    # dropped: English-only, no ISBN, only English-market ISBM's,
    # no language field, missing title
    assert [b.isbn13 for b in spanish_books] == ["9788437604947", "9789500712347"]


def test_complete_work_is_fully_mapped(spanish_books) -> None:
    book = spanish_books[0]
    assert book.title == "Complete work"
    assert book.authors == ["Ana García"]
    assert book.description is None
    assert book.published_year == 1967
    assert book.page_count == 471
    assert book.cover_url == "https://covers.openlibrary.org/b/id/12345-M.jpg"
    assert book.genres == [
        "Fiction",
        "Magic realism",
        "Families",
        "Colombia",
        "Classics",
    ]
    assert book.rating is not None
    assert book.rating.value == Decimal("4.3")
    assert book.rating.count == 310
    assert book.rating.source == "Open Library"
    assert book.source == "open_library"


def test_picks_the_isbn_of_the_requested_language_edition() -> None:
    english = parse_open_library(load("open_library_edge_cases.json"), "en")
    # same work, but now the English-market ISBN-10 is chosen and converted
    assert english[0].title == "Complete work"
    assert english[0].isbn13 == "9780307474728"


def test_zero_rating_count_and_missing_cover_become_none(spanish_books) -> None:
    book = spanish_books[1]
    assert book.rating is None
    assert book.cover_url is None


def test_empty_response_returns_no_books() -> None:
    assert parse_open_library({"numFound": 0, "docs": []}, "es") == []


async def test_search_sends_expected_params() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url.copy_with(query=None))
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=load("open_library_edge_cases.json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        books = await search_open_library(client, "realismo mágico", "es")

    assert seen["url"] == OPEN_LIBRARY_URL
    assert seen["params"] == {
        "q": "realismo mágico language:spa",
        "fields": FIELDS,
        "limit": "20",
    }
    assert len(books) == 2


async def test_search_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await search_open_library(client, "anything", "en")
