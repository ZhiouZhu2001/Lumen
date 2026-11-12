from uuid import uuid4

import pytest

from app.observability import SearchTrace, bind_search, current_search_metrics
from app.usage import UsageUnavailable
from evals.http_run import budget_delta, budget_snapshot


def test_metrics_projection_is_detached_and_does_not_expose_request_identity():
    trace = SearchTrace(str(uuid4()), cache_hit=True, model_calls=2, model_attempts=3)
    assert current_search_metrics() is None
    with bind_search(trace):
        evidence = current_search_metrics()
        assert evidence == {"cache_hit": True, "model_calls": 2, "model_attempts": 3}
        evidence["model_attempts"] = 0
        assert current_search_metrics()["model_attempts"] == 3
        assert "search_id" not in evidence
    assert current_search_metrics() is None


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        (
            {"status": "unknown"},
            {"status": "known"},
            {"status": "unknown", "attempts": None},
        ),
        (
            {"status": "known"},
            {"status": "unknown"},
            {"status": "unknown", "attempts": None},
        ),
        (
            {"status": "known", "utc_day": "2026-11-12", "used": 7},
            {"status": "known", "utc_day": "2026-11-12", "used": 12},
            {"status": "same_utc_day", "attempts": 5},
        ),
        (
            {"status": "known", "utc_day": "2026-11-12", "used": 7},
            {"status": "known", "utc_day": "2026-11-12", "used": 7},
            {"status": "same_utc_day", "attempts": 0},
        ),
        (
            {"status": "known", "utc_day": "2026-11-12", "used": 7},
            {"status": "known", "utc_day": "2026-11-12", "used": 6},
            {"status": "inconsistent", "attempts": None},
        ),
        (
            {"status": "known", "utc_day": "2026-11-12", "used": 100},
            {"status": "known", "utc_day": "2026-11-13", "used": 1},
            {"status": "utc_rollover", "attempts": None},
        ),
    ],
)
def test_budget_delta_never_reports_a_refund_or_combines_utc_days(
    before, after, expected
):
    assert budget_delta(before, after) == expected


async def test_unknown_budget_snapshot_stays_unknown_without_initialization():
    class UnknownBudget:
        calls = 0

        async def snapshot(self):
            self.calls += 1
            raise UsageUnavailable("private storage detail")

    budget = UnknownBudget()
    assert await budget_snapshot(budget) == {"status": "unknown"}
    assert budget.calls == 1


async def test_budget_snapshot_keeps_the_server_day_and_count():
    class KnownBudget:
        async def snapshot(self):
            return {"utc_day": "2026-11-12", "used": 14, "daily_cap": 100}

    assert await budget_snapshot(KnownBudget()) == {
        "status": "known",
        "utc_day": "2026-11-12",
        "used": 14,
        "daily_cap": 100,
    }
