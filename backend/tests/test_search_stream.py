import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from app.api import search as api
from app.book_cards import BookCardBuilder
from app.config import Settings, get_settings
from app.filters import SearchFilters, constrained_query, matches_metadata
from app.graph.rank import Pick
from app.graph.search import UpstreamUnavailable
from app.llm import LLMError
from app.search_stream import SearchStream
from tests.test_workflow import book


class Graph:
    def __init__(self, failure=None, count=5):
        self.failure = failure
        self.count = count
        self.input = None

    async def astream(self, state, **kwargs):
        assert kwargs == {"stream_mode": "updates"}
        self.input = state.copy()
        if self.failure:
            raise self.failure
        books = [book(n) for n in range(self.count)]
        yield {"parse_query": {"request_understood": bool(self.count)}}
        yield {"search": {"candidates": books}}
        yield {
            "rank_and_explain": {
                "picks": [
                    Pick(
                        isbn13=b.isbn13, rank=i + 1, reason="A sad novel about the sea."
                    )
                    for i, b in enumerate(books)
                ]
            }
        }


def decode(text):
    return [
        (block.splitlines()[0][7:], json.loads(block.splitlines()[1][6:]))
        for block in text.strip().split("\n\n")
    ]


@pytest.mark.parametrize(
    ("length", "pages", "expected"),
    [
        ("short", 200, True),
        ("short", 201, False),
        ("medium", 200, False),
        ("medium", 201, True),
        ("medium", 400, True),
        ("medium", 401, False),
        ("long", 400, False),
        ("long", 401, True),
        ("short", None, False),
    ],
)
def test_length_boundaries_require_metadata(length, pages, expected):
    assert (
        matches_metadata(
            book(0).model_copy(update={"page_count": pages}),
            SearchFilters(length=length),
        )
        is expected
    )


@pytest.mark.parametrize(
    ("year", "expected"),
    [(2009, False), (2010, True), (2019, True), (2020, False), (None, False)],
)
def test_publication_decade_boundaries(year, expected):
    assert (
        matches_metadata(
            book(0).model_copy(update={"published_year": year}),
            SearchFilters(era="2010s"),
        )
        is expected
    )


def test_filters_preserve_explicit_constraints_and_reject_retired_free_mode():
    query = constrained_query(
        "novela mar",
        SearchFilters(genre="literary fiction", era="2010s", length="short"),
    )
    assert all(
        term in query
        for term in ("novela mar", "literary fiction", "2010-2019", "200 pages")
    )
    for data in (
        {"free_only": True},
        {"era": "2015"},
        {"length": "tiny"},
        {"genre": ""},
    ):
        with pytest.raises(ValidationError):
            SearchFilters.model_validate(data)


async def test_http_stream_keeps_rank_order_and_never_calls_retired_source(monkeypatch):
    from tests.usage_fixtures import allow_searches

    app = FastAPI()
    allow_searches(app)
    app.include_router(api.router)
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="postgresql+asyncpg://test", redis_url="redis://test"
    )
    graph = Graph()
    observed = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: pytest.fail("No lookup without author metadata")
        )
    ) as outgoing:
        stream = SearchStream(
            graph,
            BookCardBuilder(outgoing),
            observer=lambda *args: observed.append(args),
        )
        monkeypatch.setattr(api, "get_search_stream", lambda *_: stream)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/search",
                headers={"Accept": "text/event-stream"},
                json={
                    "query": "novela mar",
                    "language": "es",
                    "filters": {"genre": "fiction"},
                },
            )
            rejected = await client.post(
                "/api/search",
                headers={"Accept": "text/event-stream"},
                json={
                    "query": "novela mar",
                    "language": "es",
                    "filters": {"free_only": True},
                },
            )
    assert rejected.status_code == 422
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["x-accel-buffering"] == "no"
    assert "no-transform" in r.headers["cache-control"]
    events = decode(r.text)
    cards = [data for event, data in events if event == "book"]
    assert [c["rank"] for c in cards] == [1, 2, 3, 4, 5]
    assert events[-1][0] == "done" and events[-1][1]["total"] == 5
    assert all(
        {l["store"] for l in c["links"]} == {"amazon_es", "casa_del_libro", "abacus"}
        for c in cards
    )
    assert graph.input["filters"].genre == "fiction"
    assert len(observed) == 1
    assert "candidate_evidence" not in r.text


@pytest.mark.parametrize(
    ("failure", "count", "code"),
    [
        (None, 0, "no_results"),
        (LLMError("private provider secret"), 5, "llm_failed"),
        (UpstreamUnavailable("private API URL"), 5, "upstream_unavailable"),
        (ValueError("private internal data"), 5, "llm_failed"),
    ],
)
async def test_stream_errors_are_friendly_and_terminal(failure, count, code):
    async with httpx.AsyncClient() as client:
        stream = SearchStream(Graph(failure, count), BookCardBuilder(client))
        text = "".join(
            [
                event
                async for event in stream.events("novela mar", "es", SearchFilters())
            ]
        )
    events = decode(text)
    assert events[-2][0] == "error" and events[-2][1]["code"] == code
    assert events[-1][0] == "done" and events[-1][1]["total"] == 0
    assert "private" not in text


async def test_cancelled_search_does_not_continue_or_emit_done():
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    class WaitingGraph:
        async def astream(self, *_args, **_kwargs):
            entered.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
            yield {}

    async with httpx.AsyncClient() as client:
        stream = SearchStream(WaitingGraph(), BookCardBuilder(client)).events(
            "novela mar", "es", SearchFilters()
        )
        assert "parsing" in await anext(stream)
        task = asyncio.create_task(anext(stream))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()


def test_retired_provider_cannot_be_reenabled_by_config():
    from app.channels.rules import StoreRule

    rule = StoreRule(
        id="gutenberg",
        label="Project Gutenberg",
        host="gutenberg.org",
        languages=["en"],
        formats=["free"],
        mode="lookup",
        provider="gutenberg",
    )
    with pytest.raises(ValueError, match="Only Apple Books"):
        BookCardBuilder(None, rules=[rule])
