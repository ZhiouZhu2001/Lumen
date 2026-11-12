import asyncio
import io
import json
import logging
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.book_cards import BookCardBuilder
from app.filters import SearchFilters
from app.graph import workflow
from app.llm import LLMError
from app.observability import (
    JsonFormatter,
    JsonHandler,
    SearchTrace,
    bind_search,
    configure_logging,
    instrument_node,
    model_attempt_reserved,
    model_call,
)
from app.search_cache import CompletedSearch
from app.search_stream import SearchStream
from app.usage import BudgetTransport, UsageLimited
from tests.test_search_stream import Graph, decode
from tests.test_workflow import BOOKS, chosen, parsed, scripted_model, stub_sources


@pytest.fixture
def logs():
    app = logging.getLogger("app")
    previous = app.handlers[:], app.level, app.propagate
    output = io.StringIO()
    handler = JsonHandler(output)
    handler.setFormatter(JsonFormatter())
    app.handlers = [handler]
    app.setLevel(logging.INFO)
    app.propagate = False
    try:
        yield lambda: [json.loads(line) for line in output.getvalue().splitlines()]
    finally:
        app.handlers, level, app.propagate = previous
        app.setLevel(level)


def test_json_allowlist_never_formats_payloads_exceptions_or_unknown_messages(logs):
    secret = "private-query-key-and-ip-198.51.100.1"
    logger = logging.getLogger("app.tests")
    try:
        raise ValueError(secret)
    except ValueError:
        logger.exception(
            "unknown message %s", secret, extra={"query": secret, "url": secret}
        )
    logger.warning(
        "catalog_item_invalid", extra={"source": "google_books", "candidate": secret}
    )
    assert logs()[0]["event"] == "application_event"
    assert logs()[1]["source"] == "google_books"
    assert secret not in json.dumps(logs())
    assert set(logs()[0]) == {"timestamp", "level", "event"}


def test_invalid_extra_values_are_omitted_without_losing_the_event(logs):
    logging.getLogger("app.tests").info(
        "search_progress",
        extra={
            "search_id": "not-a-uuid",
            "node": [],
            "source": {},
            "outcome": [],
            "error_code": {},
            "duration_ms": float("nan"),
            "elapsed_ms": -1,
            "model_calls": True,
            "model_attempts": -1,
            "cache_hit": "false",
        },
    )
    assert set(logs()[0]) == {"timestamp", "level", "event"}


def test_configuration_is_idempotent_and_does_not_enable_root_or_http_logs(logs):
    app = logging.getLogger("app")
    root = logging.getLogger()
    root_state = root.handlers[:], root.level
    http_level = logging.getLogger("httpx").level
    handler = app.handlers[0]
    configure_logging()
    configure_logging()
    assert app.handlers == [handler] and not app.propagate
    assert (root.handlers, root.level) == root_state
    assert logging.getLogger("httpx").level == http_level
    logging.getLogger("app.tests").info("search_started")
    assert len(logs()) == 1


async def test_real_graph_nodes_log_individual_durations_and_logical_calls(
    monkeypatch, logs
):
    stub_sources(monkeypatch, BOOKS)
    model = scripted_model(parsed("novela mar"), chosen(BOOKS))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("No real catalog call"))
    ) as client:
        graph = workflow.build_graph(model, client)
        text = "".join(
            [
                frame
                async for frame in SearchStream(graph, BookCardBuilder(client)).events(
                    "novela mar", "es", SearchFilters()
                )
            ]
        )
    terminal = decode(text)[-1][1]
    nodes = [record for record in logs() if record["event"] == "node_finished"]
    assert [node["node"] for node in nodes] == [
        "parse_query",
        "search",
        "rank_and_explain",
    ]
    assert [node["model_calls"] for node in nodes] == [1, 0, 1]
    assert all(
        node["duration_ms"] >= 0 and node["search_id"] == terminal["search_id"]
        for node in nodes
    )
    summary = next(record for record in logs() if record["event"] == "search_finished")
    assert summary["outcome"] == "completed" and summary["book_count"] == 5
    assert summary["model_calls"] == 2 and summary["model_attempts"] == 0
    assert not summary["cache_hit"]
    assert "novela mar" not in json.dumps(logs())


async def test_parallel_nodes_keep_request_and_node_counters_separate(logs):
    traces = [SearchTrace(str(uuid4())), SearchTrace(str(uuid4()))]

    async def run(trace, count):
        async def node(_):
            for _ in range(count):
                with model_call():
                    await asyncio.sleep(0)
                    model_attempt_reserved()
            return {}

        with bind_search(trace):
            await instrument_node("parse_query", node)({})

    await asyncio.gather(run(traces[0], 1), run(traces[1], 2))
    nodes = [record for record in logs() if record["event"] == "node_finished"]
    by_id = {record["search_id"]: record for record in nodes}
    for trace, count in zip(traces, [1, 2], strict=True):
        assert trace.model_calls == trace.model_attempts == count
        assert (
            by_id[trace.search_id]["model_calls"]
            == by_id[trace.search_id]["model_attempts"]
            == count
        )


async def test_budget_denial_is_not_counted_as_a_reserved_attempt(logs):
    guards = type(
        "Guards",
        (),
        {"consume_ai": AsyncMock(side_effect=UsageLimited(10, daily=True))},
    )()
    trace = SearchTrace(str(uuid4()))
    async with httpx.AsyncClient(
        transport=BudgetTransport(
            guards, httpx.MockTransport(lambda _: pytest.fail("No send after denial"))
        )
    ) as client:
        with bind_search(trace), pytest.raises(UsageLimited), model_call():
            await client.post("https://model.invalid/request")
    assert trace.model_calls == 1 and trace.model_attempts == 0
    assert not [
        record for record in logs() if record["event"] == "model_attempt_reserved"
    ]


async def test_send_failure_keeps_the_committed_reservation_count(logs):
    guards = type("Guards", (), {"consume_ai": AsyncMock()})()
    trace = SearchTrace(str(uuid4()))

    def fail(request):
        raise httpx.ConnectError("private-provider-url", request=request)

    async with httpx.AsyncClient(
        transport=BudgetTransport(guards, httpx.MockTransport(fail))
    ) as client:
        with bind_search(trace), pytest.raises(httpx.ConnectError), model_call():
            await client.post("https://model.invalid/request")
    assert trace.model_calls == trace.model_attempts == 1
    assert (
        next(record for record in logs() if record["event"] == "model_call_finished")[
            "outcome"
        ]
        == "failed"
    )
    assert "private-provider-url" not in json.dumps(logs())


async def test_interleaved_streams_restore_context_and_close_safely_in_another_task(
    logs,
):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("No network"))
    ) as client:
        first = SearchStream(Graph(), BookCardBuilder(client)).events(
            "private first", "es", SearchFilters()
        )
        second = SearchStream(Graph(), BookCardBuilder(client)).events(
            "private second", "es", SearchFilters()
        )
        await anext(first)
        await anext(second)
        logging.getLogger("app.tests").info("search_progress")
        assert "search_id" not in logs()[-1]
        while "event: book" not in await anext(first):
            pass
        await asyncio.create_task(first.aclose())
        text = "".join([frame async for frame in second])
        assert decode(text)[-1][1]["total"] == 5
    summaries = [record for record in logs() if record["event"] == "search_finished"]
    assert (
        len(summaries) == 2 and summaries[0]["search_id"] != summaries[1]["search_id"]
    )
    assert summaries[0]["outcome"] == "cancelled" and summaries[0]["book_count"] == 1
    assert summaries[1]["outcome"] == "completed"


async def test_cancelling_a_running_node_logs_cancellation_and_releases_context(logs):
    started = asyncio.Event()

    async def node(_):
        with model_call():
            started.set()
            await asyncio.Event().wait()

    class WaitingGraph:
        async def astream(self, state, **_):
            await instrument_node("search", node)(state)
            yield {}

    async with httpx.AsyncClient() as client:
        stream = SearchStream(WaitingGraph(), BookCardBuilder(client)).events(
            "private", "es", SearchFilters()
        )
        await anext(stream)
        pending = asyncio.create_task(anext(stream))
        await started.wait()
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        await stream.aclose()
    assert (
        next(record for record in logs() if record["event"] == "node_finished")[
            "outcome"
        ]
        == "cancelled"
    )
    assert (
        next(record for record in logs() if record["event"] == "search_finished")[
            "outcome"
        ]
        == "cancelled"
    )
    logging.getLogger("app.tests").info("search_progress")
    assert "search_id" not in logs()[-1]


async def test_failures_log_safe_codes_and_cached_replay_uses_no_model_calls(logs):
    observed = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("No network"))
    ) as client:
        failed = SearchStream(
            Graph(failure=LLMError("private exception")), BookCardBuilder(client)
        )
        _ = [frame async for frame in failed.events("private", "es", SearchFilters())]
        successful = SearchStream(
            Graph(),
            BookCardBuilder(client),
            observer=lambda *args: observed.append(args),
        )
        _ = [
            frame async for frame in successful.events("private", "es", SearchFilters())
        ]
        cached = CompletedSearch(state=observed[0][1], cards=observed[0][2])
        replay = SearchStream(None, None, cached=cached)
        _ = [frame async for frame in replay.events("private", "es", SearchFilters())]
    summaries = [record for record in logs() if record["event"] == "search_finished"]
    assert (
        summaries[0]["outcome"] == "failed"
        and summaries[0]["error_code"] == "llm_failed"
    )
    assert summaries[-1]["cache_hit"] and summaries[-1]["outcome"] == "completed"
    assert summaries[-1]["model_calls"] == summaries[-1]["model_attempts"] == 0
    assert "private" not in json.dumps(logs())


async def test_a_broken_log_sink_cannot_fail_the_search(logs):
    class BrokenOutput:
        def write(self, _):
            raise OSError("private sink detail")

    logging.getLogger("app").handlers[0].setStream(BrokenOutput())
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("No network"))
    ) as client:
        stream = SearchStream(Graph(), BookCardBuilder(client))
        text = "".join(
            [frame async for frame in stream.events("private", "es", SearchFilters())]
        )
    assert decode(text)[-1][1]["total"] == 5


async def test_an_empty_result_is_a_completed_search_not_an_operational_outage(logs):
    async with httpx.AsyncClient() as client:
        stream = SearchStream(Graph(count=0), BookCardBuilder(client))
        text = "".join(
            [frame async for frame in stream.events("private", "es", SearchFilters())]
        )
    assert decode(text)[-1][1]["total"] == 0
    summary = next(record for record in logs() if record["event"] == "search_finished")
    assert summary["outcome"] == "completed" and summary["error_code"] == "no_results"
    assert (
        summary["book_count"]
        == summary["model_calls"]
        == summary["model_attempts"]
        == 0
    )
