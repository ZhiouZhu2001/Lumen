from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.api import search as api
from app.config import Settings, get_settings
from app.filters import SearchFilters
from app.search_stream import SearchStream
from app.usage import UsageLimited, UsageUnavailable
from tests.test_search_stream import decode
from tests.usage_fixtures import allow_searches


@pytest.mark.parametrize("sse", [False, True])
@pytest.mark.parametrize(
    ("error", "status"),
    [(UsageLimited(35), 429), (UsageUnavailable("private Redis URL"), 503)],
)
async def test_admission_denial_blocks_both_paths_before_external_calls(
    sse, error, status, monkeypatch
):
    app = FastAPI()
    app.include_router(api.router)
    allow_searches(app)
    app.state.usage.admit_search.side_effect = error
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="test", redis_url="test"
    )
    monkeypatch.setattr(
        api,
        "get_search_stream",
        lambda *_: pytest.fail("Unexpected model construction"),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/search",
            headers={"accept": "text/event-stream"} if sse else {},
            json={"query": "novela mar", "language": "es"},
        )
    assert response.status_code == status and "private" not in response.text
    if status == 429:
        assert response.headers["retry-after"] == "35"
    app.state.search_cache.get_completed.assert_not_awaited()


async def test_spoofed_forwarded_header_does_not_change_untrusted_identity():
    app = FastAPI()
    app.include_router(api.router)
    allow_searches(app)
    app.state.usage.admit_search.side_effect = UsageLimited(10)
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="test", redis_url="test"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("192.0.2.4", 123)),
        base_url="http://test",
    ) as client:
        await client.post(
            "/api/search",
            headers={"x-forwarded-for": "198.51.100.1"},
            json={"query": "novela", "language": "es"},
        )
    app.state.usage.admit_search.assert_awaited_once_with("192.0.2.4")


@pytest.mark.parametrize("failure", [UsageLimited(20, daily=True), UsageUnavailable()])
async def test_midstream_budget_denial_is_terminal_and_never_saved(failure):
    class Graph:
        async def astream(self, *_args, **_kwargs):
            raise failure
            yield {}

    repo = type("Repo", (), {"save_completed": AsyncMock()})()
    cache = type("Cache", (), {"put_completed": AsyncMock()})()
    stream = SearchStream(Graph(), None, repository=repo, cache=cache)
    text = "".join(
        [s async for s in stream.events("novela mar", "es", SearchFilters())]
    )
    events = decode(text)
    assert events[-2][0] == "error" and events[-1][0] == "done"
    repo.save_completed.assert_not_awaited()
    cache.put_completed.assert_not_awaited()
