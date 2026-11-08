import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from langchain_openai import ChatOpenAI

from app.api.search import router
from app.cache import JsonCache
from app.config import Settings, get_settings
from app.graph.parse_query import ParsedQuery
from app.llm import ask_structured
from app.search_cache import SearchCache, cache_key
from app.usage import BudgetTransport, UsageGuards, UsageLimited
from integration_tests.test_persistence import counts
from tests.persistence_fixtures import completed
from tests.test_search_stream import decode


async def test_atomic_shared_hourly_limit_under_concurrency(redis_scope):
    redis, prefix = redis_scope
    guards = [UsageGuards(redis, 100, namespace=prefix) for _ in range(2)]
    results = await asyncio.gather(
        *[guards[i % 2].admit_search("192.0.2.1") for i in range(35)],
        return_exceptions=True,
    )
    assert sum(value is None for value in results) == 20
    assert sum(isinstance(value, UsageLimited) for value in results) == 15
    await guards[0].admit_search("192.0.2.2")
    keys = [key async for key in redis.scan_iter(match=prefix + ":ip:*")]
    assert len(keys) == 2
    assert all(0 < ttl <= 3600 for ttl in [await redis.ttl(key) for key in keys])
    assert sorted([int(await redis.get(key)) for key in keys]) == [1, 20]


async def test_atomic_daily_budget_old_buckets_do_not_block_current_day(redis_scope):
    redis, prefix = redis_scope
    seconds, _ = await redis.time()
    await redis.set(f"{prefix}:ai:{seconds // 86400 - 1}", "100", ex=1)
    guards = UsageGuards(redis, 5, namespace=prefix)
    results = await asyncio.gather(
        *[guards.consume_ai() for _ in range(15)], return_exceptions=True
    )
    assert sum(value is None for value in results) == 5
    denied = [value for value in results if isinstance(value, UsageLimited)]
    assert len(denied) == 10 and all(value.daily for value in denied)
    with pytest.raises(UsageLimited):
        await guards.check_daily()
    key = f"{prefix}:ai:{seconds // 86400}"
    assert int(await redis.get(key)) == 5
    assert 0 < await redis.ttl(key) <= 86400


async def test_json_cache_ttl_corruption_and_size_limits(redis_scope):
    redis, prefix = redis_scope
    cache = JsonCache(redis)
    key = prefix + ":cache"
    await cache.put(key, {"query": "novela"}, 60)
    assert await cache.get(key) == {"query": "novela"}
    assert 0 < await redis.ttl(key) <= 60
    await redis.set(key, "broken json", ex=60)
    assert await cache.get(key) is None
    await cache.delete(key)
    await cache.put(key, {"data": "x" * 2_000_001}, 60)
    assert await redis.exists(key) == 0


@pytest.mark.parametrize("cap", [1, 3])
async def test_actual_sdk_retries_are_each_charged_before_transport(redis_scope, cap):
    redis, prefix = redis_scope
    guards = UsageGuards(redis, cap, namespace=prefix)
    requests = []

    def handler(request):
        requests.append(request)
        if len(requests) < 3:
            return httpx.Response(500, json={"error": {"message": "temporary failure"}})
        return httpx.Response(
            200,
            json={
                "id": "recorded",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-5.4-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "searches": ["novela mar"],
                                    "genre": "fiction",
                                    "is_book_request": True,
                                }
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )

    async with httpx.AsyncClient(
        transport=BudgetTransport(guards, httpx.MockTransport(handler))
    ) as client:
        model = ChatOpenAI(
            model="gpt-5.4-mini",
            api_key="test-not-a-secret",
            http_async_client=client,
            max_retries=2,
        )
        if cap == 1:
            with pytest.raises(UsageLimited):
                await ask_structured(model, ParsedQuery, "system", "request")
        else:
            result = await ask_structured(model, ParsedQuery, "system", "request")
            assert result.searches == ["novela mar"]
    assert len(requests) == cap


async def test_source_cache_cannot_overwrite_newer_book_snapshot(storage):
    repository, engine = storage
    state, cards = completed(1)
    recent = datetime.now(UTC) - timedelta(minutes=1)
    state["candidates"][0].catalog_fetched_at = recent
    await repository.save_completed(uuid4(), state, cards, 10)
    stale = deepcopy(state)
    stale["candidates"][0].catalog_fetched_at = recent - timedelta(hours=1)
    stale["candidates"][0].title += " older source response"
    old_cards = deepcopy(cards)
    old_cards[0].title = stale["candidates"][0].title
    await repository.save_completed(uuid4(), stale, old_cards, 20)
    book = await repository.get_book(cards[0].isbn13)
    assert book.title == cards[0].title and book.fetched_at == recent
    assert await counts(engine) == [1, 2, 2]


async def test_result_hit_stays_available_at_daily_cap_and_does_not_refresh_book(
    storage, redis_scope
):
    repository, engine = storage
    redis, prefix = redis_scope
    state, cards = completed(1)
    await repository.save_completed(uuid4(), state, cards, 20)
    before = await repository.get_book(cards[0].isbn13)
    # Keep both cache and usage data inside this test's disposable key namespace.
    cache = SearchCache(JsonCache(redis), "test")
    cache.key = lambda kind, payload: cache_key(prefix + ":cache:" + kind, payload)
    await cache.put_completed(state, cards)
    guards = UsageGuards(redis, 1, namespace=prefix)
    await guards.consume_ai()
    app = FastAPI()
    app.include_router(router)
    app.state.usage = guards
    app.state.repository = repository
    app.state.search_cache = cache
    app.state.book_cards = None
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="test", redis_url="test"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/api/search",
            headers={"accept": "text/event-stream"},
            json={"query": state["query"], "language": "es"},
        )
        miss = await client.post(
            "/api/search",
            headers={"accept": "text/event-stream"},
            json={"query": "another request", "language": "es"},
        )
    events = decode(r.text)
    assert r.status_code == 200 and events[-1][0] == "done"
    assert not any(event == "error" for event, _ in events)
    assert miss.status_code == 503 and int(miss.headers["retry-after"]) > 0
    assert (await repository.get_book(cards[0].isbn13)).fetched_at == before.fetched_at
    assert await counts(engine) == [1, 2, 2]
