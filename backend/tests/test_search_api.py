import httpx
import pytest

from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_search_returns_books(client) -> None:
    response = await client.post(
        "/api/search", json={"query": "realismo mágico", "language": "es"}
    )
    assert response.status_code == 200
    books = response.json()["books"]
    assert len(books) == 1
    assert books[0]["language"] == "es"


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
