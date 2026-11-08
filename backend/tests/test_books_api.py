from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.books import router
from app.repository import StorageUnavailable


@pytest.mark.parametrize("isbn", ["bad", "0307474720", "9780141439519"])
async def test_invalid_isbns_are_rejected_without_storage_access(isbn):
    app = FastAPI()
    app.include_router(router)
    app.state.repository = type("Repository", (), {"get_book": AsyncMock()})()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/books/" + isbn)
    assert response.status_code == 422
    app.state.repository.get_book.assert_not_awaited()


async def test_database_failure_is_a_sanitized_503():
    app = FastAPI()
    app.include_router(router)
    app.state.repository = type(
        "Repository",
        (),
        {"get_book": AsyncMock(side_effect=StorageUnavailable("private database URL"))},
    )()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/books/9780141439518")
    assert (
        response.status_code == 503
        and response.json()["detail"]["code"] == "upstream_unavailable"
    )
    assert "private" not in response.text
