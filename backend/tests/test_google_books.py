import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.sources.google_books import (
    GOOGLE_BOOKS_URL,
    parse_google_books,
    search_google_books,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def books():
    return parse_google_books(load("google_books_edge_cases.json"), "es")


def test_keeps_only_usable_books(books) -> None:
    assert [b.isbn13 for b in books] == [
        "9780307474728",
        "9788437604947",
        "9788401242267",
    ]


def test_complete_book_is_fully_mapped(books) -> None:
    book = books[0]
    assert book.title == "Complete book"
    assert book.authors == ["Ana García", "Luis Pérez"]
    assert book.published_year == 2009
    assert book.page_count == 496
    assert book.genres == ["Fiction"]
    assert book.cover_url == "https://books.google.com/thumb"
    assert book.rating is not None
    assert book.rating.value == Decimal("4.5")
    assert book.rating.count == 120
    assert book.source == "google_books"


def test_isbn10_is_converted_and_year_only_date_is_parsed(books) -> None:
    book = books[1]
    assert book.isbn13 == "9788437604947"
    assert book.published_year == 1967


def test_rating_without_count_is_dropped_and_zero_pages_is_none(books) -> None:
    book = books[2]
    assert book.rating is None
    assert book.page_count is None


def test_empty_response_returns_no_books() -> None:
    assert parse_google_books({"kind": "books#volumes", "totalItems": 0}, "es") == []


async def test_search_sends_expected_params() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url.copy_with(query=None))
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json=load("google_books_edge_cases.json"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        books = await search_google_books(client, "realismo mágico", "es", api_key="k")

    assert seen["url"] == GOOGLE_BOOKS_URL
    assert seen["params"] == {
        "q": "realismo mágico",
        "langRestrict": "es",
        "printType": "books",
        "maxResults": "20",
        "key": "k",
    }
    assert len(books) == 3


async def test_search_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"code": 429}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await search_google_books(client, "anything", "en")


def test_real_response_parses() -> None:
    books = parse_google_books(load("google_books_real_es.json"), "es")
    assert books, "a real response should contain at least one usable book"
    assert all(b.language == "es" for b in books)
