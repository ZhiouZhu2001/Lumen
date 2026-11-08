from copy import deepcopy
from unittest.mock import AsyncMock

import httpx
import pytest

from app.catalog_cache import CatalogCacheTransport
from app.filters import SearchFilters
from app.graph.workflow import build_graph
from app.repository import SearchRepository
from app.search_cache import SearchCache
from app.search_stream import SearchStream
from tests.persistence_fixtures import completed
from tests.test_search_stream import decode
from tests.usage_fixtures import MemoryCache


async def test_result_cache_keeps_language_filters_query_and_model_separate():
    memory = MemoryCache()
    cache = SearchCache(memory, "model-a")
    state, cards = completed(1)
    repo = SearchRepository(None)
    await cache.put_completed(state, cards)
    assert await cache.get_completed(state["query"], "es", SearchFilters(), repo)
    for query, lang, filters in [
        (state["query"], "en", SearchFilters()),
        (state["query"] + " ", "es", SearchFilters()),
        (state["query"], "es", SearchFilters(length="short")),
    ]:
        assert await cache.get_completed(query, lang, filters, repo) is None
    assert (
        await SearchCache(memory, "model-b").get_completed(
            state["query"], "es", SearchFilters(), repo
        )
        is None
    )
    assert list(memory.ttls.values()) == [21600]


@pytest.mark.parametrize(
    "damage", ["isbn", "reason", "query", "filter", "link", "format", "structure"]
)
async def test_corrupt_cache_never_becomes_recommendations(damage):
    memory = MemoryCache()
    cache = SearchCache(memory, "test")
    state, cards = completed(1)
    await cache.put_completed(state, cards)
    key = cache.result_key(state["query"], "es", SearchFilters())
    value = deepcopy(memory.values[key])
    if damage == "isbn":
        value["cards"][0]["isbn13"] = "9780141439518"
    if damage == "reason":
        value["cards"][0]["reason"] += " altered"
    if damage == "query":
        value["state"]["query"] = "other query"
    if damage == "filter":
        value["state"]["filters"] = {"length": "long"}
    if damage == "link":
        value["cards"][0]["links"][0]["url"] = "https://unrelated.example/book"
    if damage == "format":
        value["cards"][0]["formats"] = ["free"]
    if damage == "structure":
        value = {"state": None}
    memory.values[key] = value
    assert (
        await cache.get_completed(
            state["query"], "es", SearchFilters(), SearchRepository(None)
        )
        is None
    )
    assert key not in memory.values


async def test_cached_stream_has_no_graph_or_channel_calls_and_saves_new_search():
    memory = MemoryCache()
    cache = SearchCache(memory, "test")
    state, cards = completed(1)
    await cache.put_completed(state, cards)
    snapshot = await cache.get_completed(
        state["query"], "es", SearchFilters(), SearchRepository(None)
    )
    repo = type("Repository", (), {"save_completed": AsyncMock()})()
    stream = SearchStream(None, None, cached=snapshot, repository=repo)
    events = decode(
        "".join([s async for s in stream.events(state["query"], "es", SearchFilters())])
    )
    assert [v["isbn13"] for e, v in events if e == "book"] == [cards[0].isbn13]
    assert events[-1][0] == "done" and events[-1][1]["limited"]
    repo.save_completed.assert_awaited_once()
    assert repo.save_completed.call_args.kwargs == {"refresh_books": False}


@pytest.mark.parametrize("status", [200, 503])
async def test_only_successful_catalog_json_is_cached(status):
    memory = MemoryCache()
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"items": []})

    async with httpx.AsyncClient(
        transport=CatalogCacheTransport(memory, httpx.MockTransport(handler))
    ) as client:
        for _ in range(2):
            await client.get(
                "https://www.googleapis.com/books/v1/volumes?q=novela&langRestrict=es"
            )
        for _ in range(2):
            await client.get("https://itunes.apple.com/search?term=novela")
    assert len(requests) == (3 if status == 200 else 4)
    assert list(memory.ttls.values()) == ([86400] if status == 200 else [])


async def test_source_cache_preserves_fetch_time_and_language_parameters():
    from app.sources.google_books import search_google_books
    from tests.test_search_api import load

    memory = MemoryCache()
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=load("google_books_real_es.json"))

    async with httpx.AsyncClient(
        transport=CatalogCacheTransport(memory, httpx.MockTransport(handler))
    ) as client:
        first = await search_google_books(client, "novela", "es")
        second = await search_google_books(client, "novela", "es")
        await search_google_books(client, "novela", "en")
    assert len(calls) == 2
    assert first[0].catalog_fetched_at is not None
    assert second[0].catalog_fetched_at == first[0].catalog_fetched_at
    assert "catalog_fetched_at" not in second[0].model_dump()


async def test_parse_cache_avoids_model_call_without_changing_bounded_graph(
    monkeypatch,
):
    from app.graph import workflow
    from app.graph.parse_query import ParsedQuery

    memory = MemoryCache()
    cache = SearchCache(memory, "test")
    parse = AsyncMock(
        return_value=ParsedQuery(searches=[], genre=None, is_book_request=False)
    )
    monkeypatch.setattr(workflow, "parse_query", parse)
    async with httpx.AsyncClient() as client:
        graph = build_graph(None, client, cache=cache)
        state = {
            "query": "zxqv blorpt",
            "language": "en",
            "filters": SearchFilters(),
            "parsed": None,
            "tried": [],
            "candidates": [],
            "retries": 0,
            "picks": [],
        }
        first = await graph.ainvoke(state)
        second = await graph.ainvoke(state)
    assert parse.await_count == 1
    assert first["model_calls"] == 1 and second["model_calls"] == 0
    assert first["picks"] == second["picks"] == []
    assert second["retries"] == 0
    assert list(memory.ttls.values()) == [604800]
