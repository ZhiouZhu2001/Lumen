"""A stalled optional provider must not hold the first stream card."""

import asyncio
import json

import httpx
import pytest

from app.book_cards import APPLE_INTERVAL, BookCardBuilder
from app.filters import SearchFilters
from app.graph.rank import Pick
from app.search_stream import SearchStream
from tests.test_book_cards import Clock, book, fixture, pick, recorded


class SingleBookGraph:
    def __init__(self, candidate, update=None):
        self.candidate = candidate
        self.update = update

    async def astream(self, state, **kwargs):
        if self.update:
            self.update()
        yield {"search": {"candidates": [self.candidate]}}
        yield {
            "rank_and_explain": {
                "picks": [
                    Pick(
                        isbn13=self.candidate.isbn13,
                        rank=1,
                        reason="A novel about relationships.",
                    )
                ]
            }
        }


async def first_book(events):
    async for frame in events:
        if frame.startswith("event: book\n"):
            return json.loads(frame.split("data: ", 1)[1])
    raise AssertionError("The stream finished without the first book")


async def test_first_book_survives_a_stalled_real_optional_channel_transport():
    candidate = book()
    started = asyncio.Event()
    release = asyncio.Event()

    async def transport(request):
        assert request.url.host == "itunes.apple.com"
        started.set()
        await release.wait()
        return httpx.Response(200, json={"results": []})

    observed = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        events = SearchStream(
            SingleBookGraph(candidate),
            BookCardBuilder(client),
            observer=lambda *values: observed.append(values),
        ).events("A novel about relationships", "en", SearchFilters())

        try:
            card = await asyncio.wait_for(first_book(events), timeout=1.5)
            assert started.is_set()
            assert {link["store"] for link in card["links"]} == {"amazon_es"}
            remaining = [frame async for frame in events]
            assert remaining[-1].startswith("event: done\n")
            assert observed[0][3][candidate.isbn13] == {"apple_books": "unavailable"}
        finally:
            release.set()
            await events.aclose()


async def test_fast_first_card_keeps_a_verified_optional_link():
    async with httpx.AsyncClient(transport=httpx.MockTransport(recorded)) as client:
        events = SearchStream(SingleBookGraph(book()), BookCardBuilder(client)).events(
            "A novel about relationships", "en", SearchFilters()
        )
        try:
            card = await first_book(events)
            assert {link["store"] for link in card["links"]} == {
                "amazon_es",
                "apple_books",
            }
        finally:
            await events.aclose()


async def test_optional_timeout_releases_transport_and_keeps_request_spacing_and_retry():
    clock = Clock()
    starts = []
    cancelled = asyncio.Event()

    async def transport(request):
        starts.append(clock())
        if len(starts) == 1:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        return httpx.Response(200, json=fixture("apple"))

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        builder = BookCardBuilder(client, clock=clock, sleep=clock.sleep)
        first = await builder.build([book()], [pick(book())], lookup_timeout=0.01)
        assert first.lookups[book().isbn13] == {"apple_books": "unavailable"}
        assert cancelled.is_set()
        second = await builder.build([book()], [pick(book())])
        assert second.lookups[book().isbn13] == {"apple_books": "matched"}
    assert len(starts) == 2 and starts[1] - starts[0] >= APPLE_INTERVAL


async def test_outer_cancellation_is_not_swallowed_as_optional_unavailability():
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def transport(request):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        builder = BookCardBuilder(client)
        task = asyncio.create_task(
            builder.build([book()], [pick(book())], lookup_timeout=10)
        )
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()


async def test_exhausted_first_book_time_does_not_start_optional_work(monkeypatch):
    from app import search_stream

    now = [0.0]
    monkeypatch.setattr(search_stream, "perf_counter", lambda: now[0])
    graph = SingleBookGraph(book(), update=lambda: now.__setitem__(0, 14.9))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: pytest.fail("No remaining optional lookup budget")
        )
    ) as client:
        events = SearchStream(graph, BookCardBuilder(client)).events(
            "A novel about relationships", "en", SearchFilters()
        )
        try:
            card = await first_book(events)
            assert {link["store"] for link in card["links"]} == {"amazon_es"}
        finally:
            await events.aclose()
