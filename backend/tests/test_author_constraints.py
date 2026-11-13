"""Exact-author regressions over the captured real wrong-author result."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.authors import (
    known_requested_authors,
    matches_authors,
)
from app.graph import workflow
from app.graph.parse_query import ParsedQuery, clean_parsed_query
from app.graph.rank import ModelPick, ModelPicks
from app.repository import SearchRepository
from app.search_cache import CompletedSearch, SearchCache
from app.search_stream import SearchStream
from tests.test_persistence_stream import SnapshotGraph
from tests.test_search_stream import decode
from tests.test_workflow import scripted_model
from tests.usage_fixtures import MemoryCache


def captured():
    return CompletedSearch.model_validate(
        json.loads(
            (
                Path(__file__).parent / "fixtures/author_mismatch_update12.json"
            ).read_text("utf-8")
        )
    )


def test_captured_wrong_author_cards_cannot_be_persisted():
    snapshot = captured()
    with pytest.raises(ValueError):
        SearchRepository(None).validate_completed(snapshot.state, snapshot.cards, 0)


async def test_bounded_graph_never_retains_other_authors_after_broadening(monkeypatch):
    snapshot = captured()
    state = snapshot.state.copy()
    state.update(parsed=None, tried=[], candidates=[], retries=0, picks=[])
    requested = ParsedQuery(
        searches=["novela mar"],
        genre="literary fiction",
        requested_authors=["Toine Heijmans"],
    )
    wider = ParsedQuery(
        searches=["novela oceano"],
        genre="literary fiction",
        requested_authors=["Herman Melville"],
    )
    proposed = ModelPicks(
        picks=[ModelPick(isbn13=c.isbn13, reason=c.reason) for c in snapshot.cards]
    )
    source = AsyncMock(return_value=snapshot.state["candidates"])
    monkeypatch.setattr(workflow, "search_candidates", source)
    model = scripted_model(requested, proposed, wider, wider)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected HTTP request"))
    ) as client:
        result = await workflow.build_graph(model, client).ainvoke(state)
    assert [p.isbn13 for p in result["picks"]] == ["9788417346201"]
    assert result["retries"] == 2 and result["model_calls"] == 4
    assert result["request_authors"] == ["Toine Heijmans"]
    assert all(
        "toine heijmans" in query.lower()
        for call in source.await_args_list
        for query in call.args[1]
    )


@pytest.mark.parametrize(
    ("query", "suggested", "expected"),
    [
        ("Novelas de Toine Heijmans", ["Toine Heijmans"], ["Toine Heijmans"]),
        (
            "Novels by Gabriel Garcia Marquez",
            ["Gabriel García Márquez"],
            ["Gabriel García Márquez"],
        ),
        ("Novels by Toine Heijmans", ["Herman Melville"], []),
        ("Short stories by Spanish authors", ["Spanish authors"], []),
        ("Short stories by Spanish authors", ["Spanish"], []),
        ("Books about Toine Heijmans", ["Toine Heijmans"], []),
        ("Libros sobre Toine Heijmans", ["Toine Heijmans"], []),
        ("Books like those by Toine Heijmans", ["Toine Heijmans"], []),
        ("Novelas como Toine Heijmans", ["Toine Heijmans"], []),
        ("Novels not by Toine Heijmans", ["Toine Heijmans"], []),
        ("Biografía de Toine Heijmans", ["Toine Heijmans"], []),
        ("Novels by John English", ["John English"], ["John English"]),
    ],
)
def test_author_parse_keeps_only_literal_authorship_requirements(
    query, suggested, expected
):
    parsed = ParsedQuery(searches=["novela"], genre=None, requested_authors=suggested)
    assert clean_parsed_query(parsed, query).requested_authors == expected


@pytest.mark.parametrize(
    ("actual", "requested", "expected"),
    [
        (["Gabriel García Márquez"], ["gabriel garcia marquez"], True),
        (["Heijmans, Toine"], ["Toine Heijmans"], True),
        (["Toine Heijmans"], ["Heijmans, Toine"], True),
        (["J. R. R. Tolkien"], ["J R R Tolkien"], True),
        (["Stephen King Jr."], ["Stephen King"], False),
        (["Herman Melville"], ["Toine Heijmans"], False),
        ([], ["Toine Heijmans"], False),
        (["Other Author", "Toine Heijmans"], ["Toine Heijmans"], True),
    ],
)
def test_catalog_names_match_conservatively(actual, requested, expected):
    book = captured().state["candidates"][0].model_copy(update={"authors": actual})
    assert matches_authors(book, requested) is expected


async def test_old_wrong_author_result_is_rejected_as_cache_miss():
    snapshot = captured()
    cache = SearchCache(MemoryCache(), "test")
    await cache.put_completed(snapshot.state, snapshot.cards)
    assert (
        await cache.get_completed(
            snapshot.state["query"],
            "es",
            snapshot.state["filters"],
            SearchRepository(None),
        )
        is None
    )


async def test_output_boundary_checks_authors_before_any_card_lookup():
    from unittest.mock import AsyncMock

    snapshot = captured()
    builder = type("Builder", (), {"build": AsyncMock()})()
    stream = SearchStream(SnapshotGraph(snapshot.state), builder)
    events = decode(
        "".join(
            [
                event
                async for event in stream.events(
                    snapshot.state["query"], "es", snapshot.state["filters"]
                )
            ]
        )
    )
    assert not any(event == "book" for event, _ in events)
    assert events[-2][1]["code"] == "llm_failed"
    builder.build.assert_not_awaited()


async def test_missing_requested_author_never_fills_results_from_other_authors(
    monkeypatch,
):
    snapshot = captured()
    others = [
        b for b in snapshot.state["candidates"] if "Toine Heijmans" not in b.authors
    ]
    monkeypatch.setattr(workflow, "search_candidates", AsyncMock(return_value=others))
    requested = ParsedQuery(
        searches=["novela mar"],
        genre="literary fiction",
        requested_authors=["Toine Heijmans"],
    )
    model = scripted_model(requested, requested, requested)
    state = snapshot.state.copy()
    state.update(parsed=None, tried=[], candidates=[], retries=0, picks=[])
    async with httpx.AsyncClient() as client:
        result = await workflow.build_graph(model, client).ainvoke(state)
    assert result["picks"] == [] and result["retries"] == 2
    assert result["model_calls"] == 3


@pytest.mark.parametrize(
    "query",
    [
        "Books about Toine Heijmans",
        "Books like those by Toine Heijmans",
        "Biografía de Toine Heijmans",
        "Books not by Toine Heijmans",
    ],
)
def test_legacy_inference_does_not_turn_other_mentions_into_author_constraints(query):
    assert known_requested_authors(query, captured().state["candidates"]) == []


def test_supplementary_author_check_catches_the_original_three_real_books():
    from evals.author_run import check_cards
    from evals.checks import EvalCase, evaluate_case

    snapshot = captured()
    case = EvalCase(
        id="es_author_regression",
        query=snapshot.state["query"],
        language="es",
        category="niche",
        filters={"era": "2010s", "length": "short"},
        expected_authors=["Toine Heijmans"],
    )
    checks = check_cards(case, snapshot.cards, 1)
    assert checks["requested_authors"] is False
    assert checks["count"] and checks["metadata_filters"] and checks["isbn_format"]
    assert evaluate_case(case, snapshot.state)["authenticity"].status == "fail"
