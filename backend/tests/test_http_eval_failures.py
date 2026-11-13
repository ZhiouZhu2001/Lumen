import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.api import search as search_api
from app.graph.parse_query import ParsedQuery
from app.graph.rank import Pick
from app.search_stream import SearchStream
from app.usage import UsageLimited
from evals import http_run
from evals.run import DEFAULT_SUITE
from tests.test_workflow import book


class Budget:
    async def snapshot(self):
        return {"utc_day": "2026-11-12", "used": 100, "daily_cap": 100}


def install_runtime(monkeypatch, *, admission_denied):
    @asynccontextmanager
    async def lifespan(app):
        app.state.daily_budget = Budget()
        app.state.repository = None
        app.state.search_cache = SimpleNamespace(
            get_completed=AsyncMock(return_value=None)
        )
        app.state.usage = SimpleNamespace(
            admit_search=AsyncMock(),
            check_daily=AsyncMock(
                side_effect=UsageLimited(60, daily=True) if admission_denied else None
            ),
        )
        yield

    monkeypatch.setattr(http_run, "lifespan", lifespan)


async def test_http_eval_retains_safe_daily_error_code_from_real_admission(
    monkeypatch, tmp_path
):
    install_runtime(monkeypatch, admission_denied=True)
    output = tmp_path / "admission.json"
    assert await http_run.run_http_live(DEFAULT_SUITE, output, 10) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert all(case["http_status"] == 503 for case in report["cases"])
    assert all(case["error_code"] == "rate_limited" for case in report["cases"])


async def test_interrupted_graph_picks_are_audit_only_not_delivered_recommendations(
    monkeypatch, tmp_path
):
    install_runtime(monkeypatch, admission_denied=False)

    class PartialGraph:
        async def astream(self, state, **kwargs):
            candidates = [
                book(index).model_copy(update={"language": state["language"]})
                for index in range(4)
            ]
            yield {
                "search": {
                    "candidates": candidates,
                    "parsed": ParsedQuery(searches=["sea"], genre="literary fiction"),
                }
            }
            yield {
                "rank_and_explain": {
                    "picks": [
                        Pick(
                            isbn13=candidate.isbn13,
                            rank=index + 1,
                            reason="A sad novel about the sea.",
                        )
                        for index, candidate in enumerate(candidates)
                    ]
                }
            }
            raise UsageLimited(60, daily=True)

    monkeypatch.setattr(
        search_api,
        "get_search_stream",
        lambda request, _: SearchStream(
            PartialGraph(), None, observer=request.app.state.search_observer
        ),
    )
    output = tmp_path / "interrupted.json"
    assert await http_run.run_http_live(DEFAULT_SUITE, output, 10) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    for case in report["cases"]:
        assert case["error_code"] == "rate_limited"
        assert not case["recommendations"]
        assert all(check["status"] == "blocked" for check in case["checks"].values())
        assert len(case["graph_recommendations"]) == 4


@pytest.mark.parametrize(
    "payload",
    [
        {"detail": {"code": "private-query-marker", "message": "private-key-marker"}},
        {"detail": {"code": ["rate_limited"]}},
        {"detail": "private-key-marker"},
    ],
)
async def test_error_reporting_retains_no_unknown_codes_or_private_messages(payload):
    response = httpx.Response(503, json=payload)
    assert await http_run.safe_http_error(response) == "http_stream_failed"


async def test_error_body_capture_is_bounded():
    response = httpx.Response(503, content=b"x" * 8193)
    assert await http_run.safe_http_error(response) == "http_stream_failed"


async def test_a_completed_empty_normal_search_fails_count_instead_of_losing_evidence(
    monkeypatch, tmp_path
):
    install_runtime(monkeypatch, admission_denied=False)

    class EmptyGraph:
        async def astream(self, state, **kwargs):
            yield {
                "search": {
                    "candidates": [],
                    "parsed": ParsedQuery(searches=["sea"], genre="literary fiction"),
                    "retries": 2,
                }
            }
            yield {"rank_and_explain": {"picks": []}}

    monkeypatch.setattr(
        search_api,
        "get_search_stream",
        lambda request, _: SearchStream(
            EmptyGraph(), None, observer=request.app.state.search_observer
        ),
    )
    output = tmp_path / "no-results.json"
    assert await http_run.run_http_live(DEFAULT_SUITE, output, 10) == 1
    report = json.loads(output.read_text("utf-8"))
    normal = [case for case in report["cases"] if case["category"] == "normal"]
    assert all(case["error_code"] == "no_results" for case in normal)
    assert all(case["checks"]["count"]["status"] == "fail" for case in normal)
