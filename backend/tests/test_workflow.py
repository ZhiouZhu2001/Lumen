"""Exercise the compiled graph with scripted models and offline book sources."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.graph import workflow
from app.graph.parse_query import ParsedQuery
from app.graph.rank import ModelPick, ModelPicks, select_for_ranking
from app.graph.search import UpstreamUnavailable
from app.graph.state import SearchState
from app.llm import LLMError
from app.sources.google_books import parse_google_books
from app.sources.isbn import isbn13_check_digit
from app.sources.schemas import BookCandidate, Language

FIXTURES = Path(__file__).parent / "fixtures"


def book(n: int, description: str | None = "A sad novel about the sea."):
    first12 = f"97884{n:07d}"
    return BookCandidate(
        isbn13=first12 + isbn13_check_digit(first12),
        title=f"Candidate {n}",
        language="es",
        description=description,
        source="google_books+open_library",
    )


BOOKS = [book(n) for n in range(5)]


def parsed(*searches: str) -> ParsedQuery:
    return ParsedQuery(searches=list(searches), genre="literary fiction")


def chosen(books: list[BookCandidate]) -> ModelPicks:
    return ModelPicks(
        picks=[
            ModelPick(isbn13=b.isbn13, reason="A sad sea story. It fits your request.")
            for b in books
        ]
    )


def scripted_model(*outputs: BaseModel | Exception) -> Mock:
    model = Mock(spec=BaseChatModel)
    model.with_structured_output.return_value.ainvoke = AsyncMock(side_effect=outputs)
    return model


def initial_state(language: Language = "es") -> SearchState:
    return SearchState(
        query="quiero una novela triste sobre el mar",
        language=language,
        parsed=None,
        tried=[],
        candidates=[],
        retries=0,
        picks=[],
    )


def stub_sources(monkeypatch, *batches: list[BookCandidate]) -> AsyncMock:
    source = AsyncMock(side_effect=batches)
    monkeypatch.setattr(workflow, "search_candidates", source)
    return source


def reject_network(request: httpx.Request) -> httpx.Response:
    pytest.fail(f"Unexpected HTTP request: {request.url.host}")


async def execute(model, handler=reject_network, language: Language = "es"):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        graph = workflow.build_graph(model, client)
        return await graph.ainvoke(initial_state(language))


@pytest.mark.parametrize("language", ["en", "es"])
async def test_five_usable_books_are_ranked_without_broadening(monkeypatch, language):
    books = [b.model_copy(update={"language": language}) for b in BOOKS]
    no_description = book(20, None).model_copy(update={"language": language})
    source = stub_sources(monkeypatch, [*books, no_description])
    output = chosen([book(99), *books, books[0], no_description])
    model = scripted_model(parsed("novela mar"), output)

    result = await execute(model, language=language)

    assert result["retries"] == 0
    assert result["tried"] == ["novela mar"]
    assert [p.isbn13 for p in result["picks"]] == [b.isbn13 for b in books]
    assert [p.rank for p in result["picks"]] == [1, 2, 3, 4, 5]
    assert all(b.language == language for b in result["candidates"])
    assert source.await_count == 1
    assert model.with_structured_output.call_count == 2


async def test_rounds_accumulate_unique_books_and_only_new_searches(monkeypatch):
    source = stub_sources(monkeypatch, BOOKS[:2], BOOKS[1:4], BOOKS[3:])
    model = scripted_model(
        parsed("novela mar"),
        chosen(BOOKS[:2]),
        parsed("NOVELA MAR", "novela naufragio"),
        chosen(BOOKS[:4]),
        parsed("novela naufragio", "novela pescadores"),
        chosen(BOOKS),
    )

    result = await execute(model)

    assert result["retries"] == 2
    assert result["tried"] == ["novela mar", "novela naufragio", "novela pescadores"]
    assert [b.isbn13 for b in result["candidates"]] == [b.isbn13 for b in BOOKS]
    assert all(b.source == "google_books+open_library" for b in result["candidates"])
    assert [call.args[1] for call in source.await_args_list] == [
        ["novela mar"],
        ["novela naufragio"],
        ["novela pescadores"],
    ]


async def test_broadening_stops_as_soon_as_enough_books_are_found(monkeypatch):
    source = stub_sources(monkeypatch, BOOKS[:2], BOOKS)
    model = scripted_model(
        parsed("novela mar"),
        chosen(BOOKS[:2]),
        parsed("novela naufragio"),
        chosen(BOOKS),
    )
    result = await execute(model)
    assert result["retries"] == 1
    assert source.await_count == 2
    assert len(result["picks"]) == 5


async def test_remaining_books_are_ranked_after_two_broadening_attempts(monkeypatch):
    source = stub_sources(monkeypatch, BOOKS[:3], BOOKS[:3], BOOKS[:3])
    model = scripted_model(
        parsed("novela mar"),
        chosen(BOOKS[:3]),
        parsed("novela naufragio"),
        chosen(BOOKS[:3]),
        parsed("novela pescadores"),
        chosen(BOOKS[:3]),
    )
    result = await execute(model)
    assert result["retries"] == 2
    assert source.await_count == 3
    assert len(result["picks"]) == 3


@pytest.mark.parametrize("description", [None, "", " \n\t "])
async def test_books_without_usable_descriptions_end_without_model_ranking(
    monkeypatch, description
):
    books = [book(n, description) for n in range(10)]
    source = stub_sources(monkeypatch, books, books, books)
    model = scripted_model(
        parsed("novela mar"), parsed("novela naufragio"), parsed("novela pescadores")
    )
    result = await execute(model)
    assert result["retries"] == 2
    assert result["picks"] == []
    assert source.await_count == 3
    assert model.with_structured_output.call_count == 3


async def test_repeated_broadened_searches_make_no_extra_source_calls(monkeypatch):
    source = stub_sources(monkeypatch, BOOKS[:2])
    model = scripted_model(
        parsed("novela mar"),
        chosen(BOOKS[:2]),
        parsed("NOVELA MAR"),
        chosen(BOOKS[:2]),
        parsed("Novela Mar"),
        chosen(BOOKS[:2]),
    )
    result = await execute(model)
    assert result["retries"] == 2
    assert result["tried"] == ["novela mar"]
    assert source.await_count == 1
    assert len(result["picks"]) == 2


async def test_valid_empty_picks_are_a_no_results_outcome(monkeypatch):
    stub_sources(monkeypatch, BOOKS, BOOKS, BOOKS)
    result = await execute(
        scripted_model(
            parsed("novela mar"),
            ModelPicks(picks=[]),
            parsed("novela naufragio"),
            ModelPicks(picks=[]),
            parsed("novela pescadores"),
            ModelPicks(picks=[]),
        )
    )
    assert result["retries"] == 2
    assert result["picks"] == []


async def test_nonempty_output_with_only_invented_isbns_is_a_model_failure(monkeypatch):
    stub_sources(monkeypatch, BOOKS, BOOKS, BOOKS)
    model = scripted_model(
        parsed("novela mar"),
        chosen([book(99)]),
        parsed("novela naufragio"),
        chosen([book(99)]),
        parsed("novela pescadores"),
        chosen([book(99)]),
    )
    with pytest.raises(LLMError, match="no valid picks"):
        await execute(model)


@pytest.mark.parametrize("stage", ["parsing", "broadening", "ranking"])
async def test_model_failures_are_not_reported_as_no_results(monkeypatch, stage):
    failure = RuntimeError("Simulated model outage")
    if stage == "parsing":
        model = scripted_model(failure)
    else:
        stub_sources(monkeypatch, BOOKS if stage == "ranking" else BOOKS[:2])
        outputs = [parsed("novela mar")]
        if stage == "broadening":
            outputs.append(chosen(BOOKS[:2]))
        model = scripted_model(*outputs, failure)
    with pytest.raises(LLMError, match="call failed"):
        await execute(model)


async def test_unsupported_structured_output_is_a_model_failure():
    model = scripted_model()
    model.with_structured_output.side_effect = NotImplementedError("Unsupported schema")
    with pytest.raises(LLMError, match="call failed"):
        await execute(model)


async def test_wrong_structured_output_type_is_a_model_failure():
    with pytest.raises(LLMError, match="call returned ModelPicks"):
        await execute(scripted_model(ModelPicks(picks=[])))


async def test_all_sources_failing_propagates_upstream_unavailable():
    model = scripted_model(parsed("novela mar"))
    with pytest.raises(UpstreamUnavailable):
        await execute(model, handler=lambda request: httpx.Response(503))
    assert model.with_structured_output.call_count == 1


@pytest.mark.parametrize("failing_host", ["www.googleapis.com", "openlibrary.org"])
async def test_one_source_failing_uses_recorded_results_from_the_other(failing_host):
    google = json.loads((FIXTURES / "google_books_real_es.json").read_text("utf-8"))
    open_library = json.loads(
        (FIXTURES / "open_library_edge_cases.json").read_text("utf-8")
    )
    eligible = select_for_ranking(parse_google_books(google, "es"))
    outputs = []
    for search in ("novela mar", "novela naufragio", "novela pescadores"):
        outputs.append(parsed(search))
        if failing_host == "openlibrary.org":
            outputs.append(chosen(eligible))
    seen = []

    def handler(request):
        seen.append(request.url.host)
        if request.url.host == failing_host:
            return httpx.Response(503)
        payload = google if request.url.host == "www.googleapis.com" else open_library
        return httpx.Response(200, json=payload)

    result = await execute(scripted_model(*outputs), handler=handler)
    assert result["retries"] == 2
    assert len(seen) == 6
    if failing_host == "openlibrary.org":
        assert {p.isbn13 for p in result["picks"]} == {b.isbn13 for b in eligible}
    else:
        assert result["candidates"]
        assert result["picks"] == []  # Open Library search entries lack descriptions.


async def test_successful_empty_catalogs_end_normally_after_two_retries():
    model = scripted_model(
        parsed("novela mar"), parsed("novela naufragio"), parsed("novela pescadores")
    )
    result = await execute(model, handler=lambda request: httpx.Response(200, json={}))
    assert result["candidates"] == []
    assert result["picks"] == []
    assert result["retries"] == 2


async def test_streamed_node_updates_follow_the_bounded_branch(monkeypatch):
    stub_sources(monkeypatch, BOOKS[:2], BOOKS)
    model = scripted_model(
        parsed("novela mar"),
        chosen(BOOKS[:2]),
        parsed("novela naufragio"),
        chosen(BOOKS),
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(reject_network)
    ) as client:
        graph = workflow.build_graph(model, client)
        nodes = [
            node
            async for update in graph.astream(initial_state(), stream_mode="updates")
            for node in update
        ]
    assert nodes == [
        "parse_query",
        "search",
        "rank_and_explain",
        "broaden",
        "search",
        "rank_and_explain",
    ]


async def test_insufficient_valid_picks_retry_and_include_new_books_beyond_old_thirty(
    monkeypatch,
):
    old = [book(n) for n in range(30)]
    fresh = [book(100), book(101)]
    source = stub_sources(monkeypatch, old, fresh)
    model = scripted_model(
        parsed("novela mar"),
        chosen(old[:3]),
        parsed("novela naufragio"),
        chosen(fresh),
    )
    result = await execute(model)
    assert result["retries"] == 1
    assert len(result["picks"]) == 5
    assert {p.isbn13 for p in result["picks"]} == {b.isbn13 for b in [*old[:3], *fresh]}
    assert source.await_count == 2
    assert model.with_structured_output.call_count == 4
    assert result["model_calls"] == 4
    assert len(result["ranking_rounds"]) == 2
    assert len(result["ranking_rounds"][0]["accepted_picks"]) == 3
    assert len(result["ranking_rounds"][1]["accepted_picks"]) == 5
    ranking_input = model.with_structured_output.return_value.ainvoke.await_args_list[
        -1
    ].args[0][1][1]
    assert all(b.isbn13 in ranking_input for b in [*old[:3], *fresh])


async def test_unsupported_names_are_rejected_and_repaired_within_retry_budget(
    monkeypatch,
):
    stub_sources(monkeypatch, BOOKS, [])
    bad = chosen(BOOKS)
    bad.picks[0].reason = "A trip to Atlantis. It fits your request."
    model = scripted_model(
        parsed("novela mar"),
        bad,
        parsed("novela naufragio"),
        chosen(BOOKS[:1]),
    )
    result = await execute(model)
    assert result["retries"] == 1
    assert len(result["picks"]) == 5
    assert all("Atlantis" not in p.reason for p in result["picks"])
    messages = model.with_structured_output.return_value.ainvoke.await_args_list
    assert "Atlantis" in messages[-1].args[0][1][1]
    assert "Atlantis" in messages[-2].args[0][1][1]


async def test_unsuitable_described_books_use_at_most_six_model_calls(monkeypatch):
    source = stub_sources(monkeypatch, BOOKS, BOOKS, BOOKS)
    model = scripted_model(
        parsed("novela mar"),
        ModelPicks(picks=[]),
        parsed("novela naufragio"),
        ModelPicks(picks=[]),
        parsed("novela pescadores"),
        ModelPicks(picks=[]),
    )
    result = await execute(model)
    assert result["retries"] == 2
    assert result["picks"] == []
    assert source.await_count == 3
    assert model.with_structured_output.call_count == 6
    assert result["model_calls"] == 6


async def test_valid_picks_survive_empty_later_rankings_and_remain_deduplicated(
    monkeypatch,
):
    stub_sources(monkeypatch, BOOKS, [], [])
    model = scripted_model(
        parsed("novela mar"),
        chosen(BOOKS[:3]),
        parsed("novela naufragio"),
        ModelPicks(picks=[]),
        parsed("novela pescadores"),
        chosen(BOOKS[:1]),
    )
    result = await execute(model)
    assert result["retries"] == 2
    assert len(result["picks"]) == 3
    assert len({p.isbn13 for p in result["picks"]}) == 3
    assert [p.rank for p in result["picks"]] == [1, 2, 3]
    assert result["model_calls"] == 6


async def test_nonsense_never_broadens_into_an_invented_reading_request(monkeypatch):
    source = stub_sources(monkeypatch, BOOKS)
    model = scripted_model(ParsedQuery(searches=[], genre=None, is_book_request=False))
    result = await execute(model)
    assert result["picks"] == []
    assert result["retries"] == 0
    assert result["model_calls"] == 1
    source.assert_not_awaited()
