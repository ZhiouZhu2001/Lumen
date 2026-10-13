import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings, get_settings
from app.http_client import make_http_client
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fake_apis(request: httpx.Request) -> httpx.Response:
    """Answer like Google Books or Open Library, using our recorded fixtures."""
    if request.url.host == "www.googleapis.com":
        return httpx.Response(200, json=load("google_books_edge_cases.json"))
    if request.url.host == "openlibrary.org":
        return httpx.Response(200, json=load("open_library_edge_cases.json"))
    return httpx.Response(404)


@pytest.fixture
async def client():
    # No real network: the app's HTTP client talks to fake_apis instead.
    app.state.http = make_http_client(transport=httpx.MockTransport(fake_apis))
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="postgresql+asyncpg://test", redis_url="redis://test"
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await app.state.http.aclose()


async def test_search_returns_merged_books_from_both_sources(client) -> None:
    response = await client.post(
        "/api/search", json={"query": "realismo mágico", "language": "es"}
    )
    assert response.status_code == 200
    books = response.json()["books"]
    assert [(b["isbn13"], b["source"]) for b in books] == [
        ("9780307474728", "google_books"),
        ("9788437604947", "google_books+open_library"),  # found by both
        ("9788401242267", "google_books"),
        ("9789500712347", "open_library"),
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"query": "ab", "language": "es"},  # query too short
        {"query": "x" * 301, "language": "es"},  # query too long
        {"query": "realismo mágico", "language": "zh"},  # unsupported language
        {"language": "es"},  # query missing
    ],
)
async def test_invalid_requests_are_rejected(client, body) -> None:
    response = await client.post("/api/search", json=body)
    assert response.status_code == 422
