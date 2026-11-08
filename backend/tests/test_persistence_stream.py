import asyncio
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.book_cards import BookCardBuilder
from app.channels.rules import load_rules
from app.filters import SearchFilters
from app.llm import LLMError
from app.repository import SearchRepository, StorageUnavailable
from app.search_stream import SearchStream
from tests.persistence_fixtures import completed
from tests.test_search_stream import decode


class SnapshotGraph:
    def __init__(self, snapshot, failure=None):
        self.snapshot = snapshot
        self.failure = failure

    async def astream(self, initial, **kwargs):
        if self.failure:
            raise self.failure
        yield {"parse_query": {"parsed": self.snapshot["parsed"]}}
        yield {
            "search": {
                "candidates": self.snapshot["candidates"],
                "tried": self.snapshot["tried"],
            }
        }
        yield {
            "rank_and_explain": {
                "picks": self.snapshot["picks"],
                "retries": self.snapshot["retries"],
            }
        }


def builder(client):
    return BookCardBuilder(
        client, rules=[rule for rule in load_rules() if rule.mode == "search"]
    )


@pytest.mark.parametrize("count", [0, 1])
async def test_search_commits_after_cards_and_before_done(count):
    state, _ = completed(count)
    events = []
    repository = Mock(spec=SearchRepository)

    async def save(search_id, captured, cards, duration_ms):
        assert sum(event == "book" for event, _ in events) == count
        assert not any(event == "done" for event, _ in events)
        assert captured["parsed"] == state["parsed"] and duration_ms >= 0
        events.append(("committed", {}))

    repository.save_completed = AsyncMock(side_effect=save)
    async with httpx.AsyncClient() as client:
        stream = SearchStream(
            SnapshotGraph(state), builder(client), repository=repository
        )
        async for frame in stream.events(state["query"], "es", SearchFilters()):
            events.extend(decode(frame))
    assert events[-2][0] == "committed" and events[-1][0] == "done"
    repository.save_completed.assert_awaited_once()


async def test_storage_failure_is_not_a_successful_completion_or_a_secret_leak():
    state, _ = completed(1)
    repository = Mock(spec=SearchRepository)
    repository.save_completed = AsyncMock(
        side_effect=StorageUnavailable("private connection credentials")
    )
    async with httpx.AsyncClient() as client:
        stream = SearchStream(
            SnapshotGraph(state), builder(client), repository=repository
        )
        text = "".join(
            [
                frame
                async for frame in stream.events(state["query"], "es", SearchFilters())
            ]
        )
    events = decode(text)
    assert events[-2][0] == "error" and events[-2][1]["code"] == "upstream_unavailable"
    assert events[-1][0] == "done" and "private" not in text


async def test_model_failure_is_not_persisted_as_a_completed_search():
    state, _ = completed(1)
    repository = Mock(spec=SearchRepository)
    repository.save_completed = AsyncMock()
    async with httpx.AsyncClient() as client:
        stream = SearchStream(
            SnapshotGraph(state, LLMError("offline")),
            builder(client),
            repository=repository,
        )
        frames = [
            frame
            async for frame in stream.events(state["query"], "es", SearchFilters())
        ]
    repository.save_completed.assert_not_awaited()
    assert decode("".join(frames))[-2][1]["code"] == "llm_failed"


async def test_cancel_during_storage_propagates_without_done():
    state, _ = completed(1)
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def save(*args):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    repository = Mock(spec=SearchRepository)
    repository.save_completed = AsyncMock(side_effect=save)
    async with httpx.AsyncClient() as client:
        iterator = SearchStream(
            SnapshotGraph(state), builder(client), repository=repository
        ).events(state["query"], "es", SearchFilters())

        async def consume():
            return [frame async for frame in iterator]

        task = asyncio.create_task(consume())
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert cancelled.is_set()
