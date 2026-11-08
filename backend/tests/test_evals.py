import json
from copy import deepcopy
from unittest.mock import AsyncMock, Mock

import pytest

from app.graph.rank import Pick
from app.graph.search import UpstreamUnavailable
from app.graph.state import SearchState
from app.llm import LLMError
from app.sources.isbn import isbn13_check_digit
from app.sources.schemas import BookCandidate
from evals.checks import (
    CHECK_NAMES,
    EvalCase,
    EvalLink,
    QueryFilters,
    QuerySuite,
    evaluate_case,
    gate_passed,
    load_suite,
    unknown_proper_words,
)
from evals.run import DEFAULT_SUITE, run_case, save_report


def state(count=5, retries=0):
    books = []
    for n in range(count):
        prefix = f"97884{n:07d}"
        books.append(
            BookCandidate(
                isbn13=prefix + isbn13_check_digit(prefix),
                title=f"Sea story {n}",
                language="es",
                description="A sad sea story about a sailor.",
                source="google_books",
            )
        )
    return SearchState(
        query="novela mar",
        language="es",
        parsed=None,
        tried=["novela mar"],
        retries=retries,
        candidates=books,
        picks=[
            Pick(isbn13=b.isbn13, rank=n + 1, reason="A sad sea story. A good match.")
            for n, b in enumerate(books)
        ],
    )


def case(**changes):
    return EvalCase(id="es_test", query="novela mar", language="es", **changes)


def links_for(result, store="amazon_es", url="https://www.amazon.es/s?k=book"):
    return {p.isbn13: [EvalLink(store=store, url=url)] for p in result["picks"]}


def test_bilingual_suite_has_the_required_coverage():
    suite = load_suite(DEFAULT_SUITE)
    assert len(suite.cases) == 20
    assert sum(c.language == "en" for c in suite.cases) == 10
    assert sum(c.category == "nonsense" for c in suite.cases) == 2


@pytest.mark.parametrize(
    "defect",
    ["count", "language", "ids", "query", "nonsense", "free", "comics", "constraints"],
)
def test_incomplete_or_duplicated_suites_are_rejected(defect):
    data = load_suite(DEFAULT_SUITE).model_dump()
    if defect == "count":
        data["cases"].pop()
    elif defect == "language":
        data["cases"][0]["language"] = "es"
    elif defect in {"ids", "query"}:
        key = "id" if defect == "ids" else "query"
        data["cases"][0][key] = data["cases"][1][key]
    else:
        for c in data["cases"]:
            if defect == "nonsense":
                c["category"] = "normal"
            elif defect == "free":
                c["filters"]["free_only"] = False
            elif defect == "comics":
                c["filters"]["genre"] = None
            else:
                c["filters"]["length"] = None
    with pytest.raises(ValueError):
        QuerySuite.model_validate(data)


def test_yaml_cannot_construct_python_objects(tmp_path):
    path = tmp_path / "unsafe.yaml"
    path.write_text("!!python/object/apply:builtins.str ['not a suite']", "utf-8")
    with pytest.raises(ValueError, match="Invalid query-suite YAML"):
        load_suite(path)


def test_all_six_checks_can_validate_complete_evidence():
    result = state()
    checks = evaluate_case(
        case(), result, links=links_for(result), first_book_sse_ms=15000
    )
    assert set(checks) == set(CHECK_NAMES)
    assert all(check.status == "pass" for check in checks.values())


def test_missing_product_evidence_is_blocked_even_when_core_results_are_valid():
    checks = evaluate_case(case(), state())
    assert checks["links"].status == "blocked"
    assert checks["latency"].status == "blocked"
    assert checks["authenticity"].status == "pass"


@pytest.mark.parametrize(
    ("count", "expected"), [(4, "fail"), (5, "pass"), (10, "pass"), (11, "fail")]
)
def test_normal_query_count_targets(count, expected):
    assert evaluate_case(case(), state(count))["count"].status == expected


def test_nonsense_must_have_no_recommendations():
    nonsense = case(category="nonsense")
    assert evaluate_case(nonsense, state(0))["count"].status == "pass"
    assert evaluate_case(nonsense, state(1))["count"].status == "fail"
    assert evaluate_case(nonsense, state(0))["latency"].status == "not_applicable"


def test_niche_fewer_than_five_requires_retry_exhaustion():
    niche = case(category="niche")
    assert evaluate_case(niche, state(2, retries=0))["count"].status == "fail"
    assert evaluate_case(niche, state(2, retries=2))["count"].status == "pass"


def test_invented_duplicate_and_wrong_language_recommendations_fail_checks():
    result = state()
    result["picks"].append(result["picks"][0])
    assert evaluate_case(case(), result)["authenticity"].status == "fail"
    result["picks"][0] = Pick(isbn13="9780000000000", rank=1, reason="Invented.")
    assert evaluate_case(case(), result)["authenticity"].status == "fail"
    result = state()
    result["candidates"][0].language = "en"
    assert evaluate_case(case(), result)["language"].status == "fail"


def test_empty_or_unsupported_recommendation_reasons_fail():
    result = state()
    result["picks"][0].reason = "A trip to Atlantis. A sad sea story."
    assert evaluate_case(case(), result)["reason"].status == "fail"
    result["picks"][0].reason = " "
    assert evaluate_case(case(), result)["reason"].status == "fail"


def test_proper_word_heuristic_normalizes_accents_and_ignores_pronoun_i():
    assert unknown_proper_words("Una historia en Cádiz.", "Cadiz") == []
    assert unknown_proper_words("A trip to Atlantis.", "A sea story") == ["Atlantis"]
    assert unknown_proper_words("Although I enjoy sea stories.", "A sea story") == []


@pytest.mark.parametrize(
    "url",
    [
        "http://amazon.es",
        "https://amazon.es.evil.test",
        "https://amazon.es:bad",
        "javascript:alert(1)",
        "https://[broken",
    ],
)
def test_invalid_or_mismatched_store_urls_fail(url):
    result = state()
    assert (
        evaluate_case(case(), result, links=links_for(result, url=url))["links"].status
        == "fail"
    )


def test_store_language_genre_and_free_only_rules():
    result = state()
    english = EvalCase(id="en_test", query="sea novel", language="en")
    spanish_store = links_for(result, "casa_del_libro", "https://www.casadellibro.com/")
    assert evaluate_case(english, result, links=spanish_store)["links"].status == "fail"
    norma = links_for(result, "norma_comics", "https://www.normacomics.com/")
    assert evaluate_case(case(), result, links=norma)["links"].status == "fail"
    for book in result["candidates"]:
        book.genres = ["Comics & Graphic Novels"]
    assert evaluate_case(case(), result, links=norma)["links"].status == "pass"
    free = case(filters=QueryFilters(free_only=True))
    assert (
        evaluate_case(free, result, links=links_for(result))["links"].status == "fail"
    )
    gutenberg = links_for(result, "gutenberg", "https://www.gutenberg.org/ebooks/1")
    assert evaluate_case(free, result, links=gutenberg)["links"].status == "pass"


def test_latency_uses_first_sse_book_target():
    assert (
        evaluate_case(case(), state(), first_book_sse_ms=15001)["latency"].status
        == "fail"
    )
    assert (
        evaluate_case(case(), state(), first_book_sse_ms=-1)["latency"].status == "fail"
    )


@pytest.mark.parametrize(
    "defect",
    [
        None,
        "partial",
        "duplicate",
        "blocked",
        "failed",
        "filters",
        "error",
        "missing_check",
        "false_na",
    ],
)
def test_merge_gate_cannot_pass_partial_or_incomplete_evidence(defect):
    cases = load_suite(DEFAULT_SUITE).cases
    records = [
        {
            "id": c.id,
            "category": c.category,
            "checks": {name: {"status": "pass"} for name in CHECK_NAMES},
        }
        for c in cases
    ]
    if defect == "partial":
        records.pop()
    elif defect == "duplicate":
        records[0] = deepcopy(records[1])
    elif defect in {"blocked", "failed", "false_na"}:
        records[0]["checks"]["links"]["status"] = {
            "blocked": "blocked",
            "failed": "fail",
            "false_na": "not_applicable",
        }[defect]
    elif defect == "filters":
        records[0]["unsupported_filters"] = ["free_only"]
    elif defect == "error":
        records[0]["error_code"] = "timeout"
    elif defect == "missing_check":
        records[0]["checks"].pop("latency")
    assert gate_passed(records, {c.id for c in cases}) is (defect is None)
    assert not gate_passed([], set())


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (TimeoutError(), "timeout"),
        (LLMError("private details"), "llm_failed"),
        (UpstreamUnavailable(), "upstream_unavailable"),
        (RuntimeError("private details"), "internal_error"),
    ],
)
async def test_failed_case_is_retained_without_false_zero_result_evidence(error, code):
    graph = Mock(ainvoke=AsyncMock(side_effect=error))
    result = await run_case(graph, case(), timeout=1)
    assert result["error_code"] == code
    assert result["candidate_isbns"] is None
    assert result["retries"] is None
    assert all(check["status"] == "blocked" for check in result["checks"].values())
    assert "private details" not in json.dumps(result)


async def test_core_runner_records_unsupported_filters_and_keeps_latency_separate():
    graph = Mock(ainvoke=AsyncMock(return_value=state()))
    result = await run_case(
        graph, case(filters=QueryFilters(free_only=True)), timeout=1
    )
    assert result["unsupported_filters"] == ["free_only"]
    assert result["first_book_sse_ms"] is None
    assert result["workflow_duration_ms"] >= 0
    assert result["checks"]["links"]["status"] == "blocked"
    assert result["checks"]["latency"]["status"] == "blocked"


async def test_saved_evidence_can_reproduce_the_checks_without_catalog_requests():
    from app.graph.parse_query import ParsedQuery
    from app.graph.rank import format_candidates, select_for_ranking
    from app.sources.schemas import BookCandidate

    captured = state()
    captured["parsed"] = ParsedQuery(searches=["novela mar"], genre="literary fiction")
    captured["candidates"][0].description = "A sea story. " * 100
    captured["candidates"][
        0
    ].cover_url = "https://example.test/unrelated-cover-metadata"
    captured["picks"][0].reason = "A trip to Atlantis. A sad sea story."
    graph = Mock(ainvoke=AsyncMock(return_value=captured))
    result = await run_case(graph, case(), timeout=1)

    assert result["parsed_query"]["genre"] == "literary fiction"
    assert result["rankable_count"] == 5
    assert result["shortlist_isbns"] == [b.isbn13 for b in captured["candidates"]]
    assert result["ranking_input"] == format_candidates(
        select_for_ranking(captured["candidates"])
    )
    assert "unrelated-cover-metadata" not in json.dumps(result)
    restored = captured.copy()
    restored["candidates"] = [
        BookCandidate.model_validate(b) for b in result["candidate_evidence"]
    ]
    assert {
        name: check.model_dump()
        for name, check in evaluate_case(case(), restored).items()
    } == result["checks"]


async def test_failed_workflow_has_no_fabricated_candidate_snapshot():
    result = await run_case(
        Mock(ainvoke=AsyncMock(side_effect=LLMError())), case(), timeout=1
    )
    for key in (
        "parsed_query",
        "rankable_count",
        "shortlist_isbns",
        "ranking_input",
        "candidate_evidence",
    ):
        assert result[key] is None


async def test_report_uses_actual_priority_shortlist_instead_of_reconstructing_first_thirty():
    captured = state()
    captured["model_calls"] = 4
    captured["ranking_rounds"] = [
        {
            "shortlist_isbns": [captured["candidates"][-1].isbn13],
            "ranking_input": "Captured priority ordering and truncation.",
        }
    ]
    result = await run_case(
        Mock(ainvoke=AsyncMock(return_value=captured)), case(), timeout=1
    )
    assert (
        result["shortlist_isbns"] == captured["ranking_rounds"][-1]["shortlist_isbns"]
    )
    assert result["ranking_input"] == captured["ranking_rounds"][-1]["ranking_input"]
    assert result["model_calls"] == 4
    assert result["ranking_rounds"] == captured["ranking_rounds"]


async def test_captured_cards_enable_link_checks_and_replay_keeps_them():
    from app.channels.schemas import CardBatch
    from evals.replay import recheck_report

    suite = load_suite(DEFAULT_SUITE)
    records = []
    for c in suite.cases:
        captured = state(0 if c.category == "nonsense" else 5)
        for b in captured["candidates"]:
            b.language = c.language
        cards = CardBatch(
            cards=[
                {
                    **b.model_dump(),
                    "rank": p.rank,
                    "reason": p.reason,
                    "links": [
                        {
                            "store": "amazon_es",
                            "label": "Amazon.es",
                            "url": f"https://www.amazon.es/s?k={b.isbn13}",
                            "formats": ["paper"],
                            "match": "isbn_search",
                        }
                    ],
                    "formats": ["paper"],
                }
                for b, p in zip(captured["candidates"], captured["picks"], strict=True)
            ],
            lookups={},
        )
        builder = Mock(build=AsyncMock(return_value=cards))
        record = await run_case(
            Mock(ainvoke=AsyncMock(return_value=captured)),
            c,
            timeout=1,
            card_builder=builder,
        )
        records.append(record)
    report = {
        "report_version": 2,
        "complete": True,
        "completed_cases": 20,
        "cases": records,
    }
    replayed = recheck_report(report, suite)
    assert [r["checks"] for r in replayed] == [r["checks"] for r in records]
    assert records[0]["checks"]["links"]["status"] == "pass"
    assert all(
        r["checks"]["latency"]["status"] in {"blocked", "not_applicable"}
        for r in records
    )
    assert (
        records[4]["checks"]["links"]["status"] == "fail"
    )  # Free-only must not pass on a search link.


@pytest.mark.parametrize("error", [TimeoutError(), ValueError("invalid pick")])
async def test_channel_failure_preserves_graph_evidence_and_cannot_pass_links(error):
    captured = state()
    builder = Mock(build=AsyncMock(side_effect=error))
    result = await run_case(
        Mock(ainvoke=AsyncMock(return_value=captured)),
        case(),
        timeout=1,
        card_builder=builder,
    )
    assert result["error_code"] is None
    assert result["channel_error"] in {"timeout", "invalid_card_input"}
    assert result["candidate_evidence"]
    assert result["checks"]["authenticity"]["status"] == "pass"
    assert result["checks"]["links"]["status"] == "blocked"


@pytest.mark.parametrize(
    ("genres", "expected"),
    [(["Novela gráfica"], "pass"), (["Tragicomic fiction"], "fail")],
)
def test_norma_rule_recognizes_spanish_genres_without_substring_false_positives(
    genres, expected
):
    captured = state()
    for b in captured["candidates"]:
        b.genres = genres
    assert (
        evaluate_case(
            case(),
            captured,
            links=links_for(captured, "norma_comics", "https://www.normacomics.com/"),
        )["links"].status
        == expected
    )


def test_checkpoint_reports_preserve_partial_status(tmp_path):
    path = tmp_path / "results" / "check.json"
    report = {"complete": False, "gate_passed": False, "cases": []}
    save_report(path, report)
    assert json.loads(path.read_text("utf-8")) == report
    report["cases"].append({"id": "es_example"})
    save_report(path, report)
    assert json.loads(path.read_text("utf-8"))["complete"] is False
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize(
    "defect", [None, "legacy", "partial", "duplicate", "missing_evidence", "query"]
)
async def test_complete_snapshot_replay_is_offline_and_rejects_incomplete_inputs(
    defect,
):
    from evals.replay import recheck_report

    suite = load_suite(DEFAULT_SUITE)
    records = []
    for c in suite.cases:
        captured = state(0 if c.category == "nonsense" else 5)
        for book in captured["candidates"]:
            book.language = c.language
        records.append(
            await run_case(Mock(ainvoke=AsyncMock(return_value=captured)), c, timeout=1)
        )
    report = {
        "report_version": 2,
        "complete": True,
        "completed_cases": 20,
        "cases": records,
    }
    if defect == "legacy":
        report.pop("report_version")
    elif defect == "partial":
        report["complete"] = False
    elif defect == "duplicate":
        records[0] = records[1]
    elif defect == "missing_evidence":
        records[0]["candidate_evidence"] = None
    elif defect == "query":
        records[0]["query"] = "changed query"
    if defect:
        with pytest.raises(ValueError):
            recheck_report(report, suite)
    else:
        replayed = recheck_report(report, suite)
        assert [r["checks"] for r in replayed] == [r["checks"] for r in records]
        assert all(r["checks"]["links"]["status"] == "blocked" for r in replayed)
