import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from app.config import Settings, get_settings
from app.http_client import make_http_client
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
GOOGLE_HOST = "www.googleapis.com"
OPEN_LIBRARY_HOST = "openlibrary.org"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fake_apis(failing: set[str] = frozenset()) -> Callable:
    """Fake Google Books and Open Library. Hosts in `failing` answer 503."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host in failing:
            return httpx.Response(503)
        if request.url.host == GOOGLE_HOST:
            return httpx.Response(200, json=load("google_books_edge_cases.json"))
        if request.url.host == OPEN_LIBRARY_HOST:
            return httpx.Response(200, json=load("open_library_edge_cases.json"))
        return httpx.Response(404)

    return handler


@pytest.fixture
async def make_client():
    """Build a test client whose outgoing API calls go to a fake handler."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="postgresql+asyncpg://test", redis_url="redis://test"
    )

    async def _make(handler: Callable) -> httpx.AsyncClient:
        app.state.http = make_http_client(transport=httpx.MockTransport(handler))
        transport = httpx.ASGITransport(app=app)
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    yield _make
    app.dependency_overrides.clear()
    await app.state.http.aclose()


async def search(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post(
        "/api/search", json={"query": "realismo mágico", "language": "es"}
    )


async def test_search_returns_merged_books_from_both_sources(make_client) -> None:
    async with await make_client(fake_apis()) as client:
        response = await search(client)
    assert response.status_code == 200
    books = response.json()["books"]
    assert [(b["isbn13"], b["source"]) for b in books] == [
        ("9780307474728", "google_books"),
        ("9788437604947", "google_books+open_library"),  # found by both
        ("9788401242267", "google_books"),
        ("9789500712347", "open_library"),
    ]


async def test_google_down_still_returns_open_library_books(make_client) -> None:
    async with await make_client(fake_apis(failing={GOOGLE_HOST})) as client:
        response = await search(client)
    assert response.status_code == 200
    sources = {b["source"] for b in response.json()["books"]}
    assert sources == {"open_library"}


async def test_open_library_down_still_returns_google_books(make_client) -> None:
    async with await make_client(fake_apis(failing={OPEN_LIBRARY_HOST})) as client:
        response = await search(client)
    assert response.status_code == 200
    sources = {b["source"] for b in response.json()["books"]}
    assert sources == {"google_books"}


async def test_both_down_returns_upstream_unavailable(make_client) -> None:
    failing = {GOOGLE_HOST, OPEN_LIBRARY_HOST}
    async with await make_client(fake_apis(failing=failing)) as client:
        response = await search(client)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "upstream_unavailable"


@pytest.mark.parametrize(
    "body",
    [
        {"query": "ab", "language": "es"},  # query too short
        {"query": "x" * 301, "language": "es"},  # query too long
        {"query": "realismo mágico", "language": "zh"},  # unsupported language
        {"language": "es"},  # query missing
    ],
)
async def test_invalid_requests_are_rejected(make_client, body) -> None:
    async with await make_client(fake_apis()) as client:
        response = await client.post("/api/search", json=body)
    assert response.status_code == 422
