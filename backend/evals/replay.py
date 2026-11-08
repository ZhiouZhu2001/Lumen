"""Recheck captured graph evidence without model, catalog or HTTP calls."""

import argparse
import hashlib
import json
from pathlib import Path

from app.channels.schemas import BookCard
from app.graph.parse_query import ParsedQuery
from app.graph.rank import Pick
from app.graph.state import SearchState
from app.sources.schemas import BookCandidate
from evals.checks import (
    CHECK_NAMES,
    CheckResult,
    EvalLink,
    QuerySuite,
    evaluate_case,
    load_suite,
)
from evals.run import DEFAULT_SUITE, summarize


def recheck_report(report: dict, suite: QuerySuite) -> list[dict]:
    if report.get("report_version") != 2:
        raise ValueError("Replay requires a version 2 report with candidate evidence")
    records = report.get("cases", [])
    if (
        report.get("complete") is not True
        or report.get("completed_cases") != 20
        or not isinstance(records, list)
        or len(records) != 20
        or not all(isinstance(record, dict) for record in records)
        or {record.get("id") for record in records} != {c.id for c in suite.cases}
    ):
        raise ValueError("Replay requires a complete report of all 20 expected cases")
    expected = {c.id: c for c in suite.cases}
    results = []
    for record in records:
        case = expected[record["id"]]
        if any(
            record.get(key) != getattr(case, key)
            for key in ("query", "language", "category")
        ):
            raise ValueError(f"Case metadata does not match the suite: {case.id}")
        if record.get("error_code"):
            checks = {
                name: CheckResult(
                    status="blocked", detail=f"Workflow failed: {record['error_code']}"
                )
                for name in CHECK_NAMES
            }
        else:
            if not isinstance(record.get("candidate_evidence"), list):
                raise ValueError(f"Missing captured candidate evidence: {case.id}")
            parsed = record.get("parsed_query")
            state = SearchState(
                query=case.query,
                language=case.language,
                parsed=ParsedQuery.model_validate(parsed) if parsed else None,
                tried=record["searches_tried"],
                candidates=[
                    BookCandidate.model_validate(b)
                    for b in record["candidate_evidence"]
                ],
                retries=record["retries"],
                picks=[Pick.model_validate(p) for p in record["recommendations"]],
            )
            captured_cards = record.get("cards")
            links = None
            if captured_cards is not None:
                cards = [BookCard.model_validate(card) for card in captured_cards]
                if len(cards) != len(state["picks"]) or {
                    card.isbn13 for card in cards
                } != {p.isbn13 for p in state["picks"]}:
                    raise ValueError(
                        f"Cards do not match the captured picks: {case.id}"
                    )
                links = {
                    card.isbn13: [
                        EvalLink(store=link.store, url=link.url) for link in card.links
                    ]
                    for card in cards
                }
            # Graph/channel duration must never manufacture an SSE latency pass.
            checks = evaluate_case(case, state, links=links)
        results.append(
            {
                **record,
                "checks": {name: check.model_dump() for name, check in checks.items()},
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    args = parser.parse_args()
    try:
        suite = load_suite(args.suite)
        report = json.loads(args.report.read_text("utf-8"))
        if not isinstance(report, dict):
            raise TypeError("The report must be a JSON object")
        if (
            report.get("suite_sha256")
            != hashlib.sha256(args.suite.read_bytes()).hexdigest()
        ):
            raise ValueError(
                "The report was captured with a different query-suite file"
            )
        results = recheck_report(report, suite)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print("Offline replay only: no live calls or new latency measurements.")
    print(json.dumps(summarize(results), indent=2))
    print(
        "Offline replay cannot supply the missing HTTP SSE evidence; this is not a live merge-gate pass."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
