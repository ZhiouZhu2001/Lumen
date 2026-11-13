"""Exercise the real validation seams with the public round-24 failures."""

import json
from pathlib import Path

import httpx
import pytest

from app.channels.rules import load_rules, search_links
from app.channels.schemas import BookCard
from app.filters import SearchFilters
from app.graph import workflow
from app.graph.parse_query import ParsedQuery
from app.graph.rank import ModelPick, ModelPicks, validate_picks
from app.graph.state import SearchState
from app.reading_intent import concedes_mismatch, matches_reader_type
from app.repository import SearchRepository
from app.search_cache import SearchCache
from app.sources.schemas import BookCandidate
from evals.checks import EvalCase, evaluate_case
from tests.test_workflow import (
    book,
    chosen,
    initial_state,
    reject_network,
    scripted_model,
    stub_sources,
)
from tests.usage_fixtures import MemoryCache

RECORDS = json.loads(
    (
        Path(__file__).parent / "fixtures/reading_type_mismatches_update24.json"
    ).read_text(encoding="utf-8")
)["records"]


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: r["candidate"]["isbn13"])
def test_actual_nonfiction_and_activity_substitutes_are_not_literary_matches(record):
    candidate = BookCandidate.model_validate(record["candidate"])
    assert not matches_reader_type(candidate, record["query"], record["genre"])


def test_actual_history_concession_is_rejected_by_the_final_pick_validator():
    record = next(r for r in RECORDS if r["case_id"] == "en_history")
    assert concedes_mismatch(record["reason"], record["query"])
    picks, feedback = validate_picks(
        ModelPicks(
            picks=[
                ModelPick(isbn13=record["candidate"]["isbn13"], reason=record["reason"])
            ]
        ),
        [BookCandidate.model_validate(record["candidate"])],
        "en",
        query=record["query"],
    )
    assert not picks
    assert feedback


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: r["candidate"]["isbn13"])
def test_rewriting_a_reason_cannot_bypass_the_final_reading_form_check(record):
    picks, _ = validate_picks(
        ModelPicks(
            picks=[
                ModelPick(
                    isbn13=record["candidate"]["isbn13"],
                    reason="It fits your request.",
                )
            ]
        ),
        [BookCandidate.model_validate(record["candidate"])],
        "en",
        query=record["query"],
        requested_genre=record["genre"],
    )
    assert not picks


@pytest.mark.parametrize(
    ("changes", "query", "genre", "expected"),
    [
        (
            {"title": "A Short History of Rain", "genres": ["History", "Fiction"]},
            "A historical novel",
            "historical fiction",
            True,
        ),
        (
            {
                "title": "A Northern Journey",
                "genres": ["History"],
                "description": "A woman arrives at an isolated village.",
            },
            "A literary novel",
            "literary fiction",
            True,
        ),
        (
            {"title": "The Coloring Book Killer", "genres": ["Fiction"]},
            "A mystery novel",
            "mystery",
            True,
        ),
        (
            {
                "title": "The History of Love",
                "genres": [],
                "description": "A novel about relationships.",
            },
            "A literary novel",
            "literary fiction",
            True,
        ),
        (
            {"title": "An Official Report of an Expedition", "genres": ["Science"]},
            "An expedition report",
            "nonfiction",
            True,
        ),
        (
            {
                "title": "Baby Dragons Coloring Book",
                "description": "A coloring book of dragons.",
            },
            "A novel about coloring books",
            "literary fiction",
            False,
        ),
        (
            {"title": "The Novel and the Sea", "genres": ["Literary Criticism"]},
            "Books about novels at sea",
            "literary criticism",
            True,
        ),
        (
            {"title": "The Novel and the Sea", "genres": ["Literary Criticism"]},
            "Literary criticism about novels",
            "literary criticism",
            True,
        ),
        (
            {"title": "A History of the Novel", "genres": ["History"]},
            "A history of the novel",
            "history",
            True,
        ),
        (
            {
                "title": "Dragones para colorear",
                "description": "Un libro para colorear con dragones.",
            },
            "Novelas de fantasía",
            "fantasy",
            False,
        ),
        (
            {
                "title": "Un libro para colorear",
                "description": "Un libro de actividades y dragones.",
            },
            "Un libro para colorear con dragones",
            "fantasy",
            True,
        ),
        (
            {"title": "Fiction: A Study", "genres": ["Non-Fiction"]},
            "Nonfiction books about novels",
            "nonfiction",
            True,
        ),
    ],
)
def test_type_filter_preserves_requested_nonfiction_and_ambiguous_fiction(
    changes, query, genre, expected
):
    assert (
        matches_reader_type(book(0).model_copy(update=changes), query, genre)
        is expected
    )


@pytest.mark.parametrize(
    "reason",
    [
        "This book is history, not a novel.",
        "This book isn't a novel; it is a historical account.",
        "This book does not fully match your fiction filter.",
        "Este libro no es una novela, es historia.",
        "Este libro es historia, no una novela.",
    ],
)
def test_direct_type_concessions_are_rejected_in_both_languages(reason):
    assert concedes_mismatch(reason, "Historical novels. Novelas históricas.")


@pytest.mark.parametrize(
    "reason",
    [
        "This novel is not only about the sea; its voyage is central.",
        "This novel isn't only about the sea; it follows a voyage.",
        "This novel is about a sailor who is not alone at sea.",
        "Esta novela no solo trata del mar, sino de una familia.",
    ],
)
def test_direct_concession_rule_does_not_reject_plot_negation(reason):
    assert not concedes_mismatch(
        reason, "A novel about the sea. Una novela sobre el mar."
    )


def test_a_nonfiction_request_can_truthfully_identify_its_book_as_not_a_novel():
    assert not concedes_mismatch(
        "This book is history, not a novel.", "A history of the novel"
    )
    assert not concedes_mismatch(
        "This book isn't a novel; it is literary criticism.",
        "Literary criticism about novels",
    )


def captured_state(record):
    candidate = BookCandidate.model_validate(record["candidate"])
    return SearchState(
        query=record["query"],
        language="en",
        filters=SearchFilters(),
        parsed=ParsedQuery(searches=["adventure"], genre=record["genre"]),
        candidates=[candidate],
        tried=["adventure"],
        retries=2,
        picks=[],
        request_genre=record["genre"],
    )


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: r["candidate"]["isbn13"])
def test_evaluation_flags_the_actual_wrong_form_even_with_a_valid_isbn(record):
    from app.graph.rank import Pick

    state = captured_state(record)
    state["picks"] = [
        Pick(isbn13=record["candidate"]["isbn13"], rank=1, reason=record["reason"])
    ]
    checks = evaluate_case(
        EvalCase(id=record["case_id"], query=record["query"], language="en"), state
    )
    assert checks["authenticity"].status == "pass"
    assert checks["reason"].status == "fail"


async def test_wrong_form_is_rejected_when_a_complete_cached_result_is_revalidated():
    from app.graph.rank import Pick

    record = RECORDS[0]
    state = captured_state(record)
    candidate = state["candidates"][0]
    reason = "It fits your request."
    state["picks"] = [Pick(isbn13=candidate.isbn13, rank=1, reason=reason)]
    links = search_links(candidate, load_rules())
    card = BookCard(
        **candidate.model_dump(),
        rank=1,
        reason=reason,
        links=links,
        formats=list(dict.fromkeys(value for link in links for value in link.formats)),
    )
    memory = MemoryCache()
    cache = SearchCache(memory, "offline-test")
    await cache.put_completed(state, [card])
    assert (
        await cache.get_completed(
            state["query"], "en", SearchFilters(), SearchRepository(None)
        )
        is None
    )
    assert cache.result_key(state["query"], "en", SearchFilters()) not in memory.values


async def test_explicit_genre_survives_parsing_and_excludes_wrong_forms_before_ranking(
    monkeypatch,
):
    wrong_form = BookCandidate.model_validate(RECORDS[1]["candidate"])
    matching = [book(index).model_copy(update={"language": "en"}) for index in range(5)]
    stub_sources(monkeypatch, [wrong_form, *matching])
    model = scripted_model(
        ParsedQuery(searches=["lighthouse reading"], genre="popular science"),
        chosen(matching),
    )
    state = initial_state("en")
    state["query"] = "A lighthouse reading list"
    state["filters"] = SearchFilters(genre="literary fiction")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(reject_network)
    ) as client:
        result = await workflow.build_graph(model, client).ainvoke(state)
    assert result["request_genre"] == "literary fiction"
    assert len(result["candidates"]) == 6
    assert wrong_form.isbn13 not in result["ranking_rounds"][0]["shortlist_isbns"]
    assert len(result["picks"]) == 5 and result["model_calls"] == 2
