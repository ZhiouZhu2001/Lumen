"""Run the full suite against live recommendation services and retain evidence."""

import argparse
import asyncio
import hashlib
import json
import math
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from app.config import get_settings
from app.graph.rank import format_candidates, select_for_ranking
from app.graph.search import UpstreamUnavailable
from app.graph.state import SearchState
from app.graph.workflow import build_graph
from app.http_client import make_http_client
from app.llm import LLMError, create_chat_model
from evals.checks import (
    CHECK_NAMES,
    CheckResult,
    EvalCase,
    evaluate_case,
    gate_passed,
    load_suite,
)

DEFAULT_SUITE = Path(__file__).with_name("queries.yaml")


def code_fingerprints() -> dict[str, str]:
    """Identify source files even when the evaluated working tree is uncommitted."""
    root = DEFAULT_SUITE.parent.parent
    paths = sorted([*(root / "app").rglob("*.py"), *(root / "evals").glob("*.py")])
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def revision_info() -> dict:
    def git(*args):
        result = subprocess.run(
            ["git", *args], capture_output=True, text=True, check=False, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    try:
        return {
            "commit": git("rev-parse", "HEAD"),
            "branch": git("branch", "--show-current"),
            "working_tree_dirty": bool(git("status", "--porcelain")),
        }
    except (OSError, subprocess.TimeoutExpired):
        return {"commit": "unknown", "branch": "unknown", "working_tree_dirty": True}


async def run_case(graph, case: EvalCase, timeout: float) -> dict:
    state = SearchState(
        query=case.query,
        language=case.language,
        parsed=None,
        tried=[],
        candidates=[],
        retries=0,
        picks=[],
    )
    error_code = None
    started = perf_counter()
    try:
        state = await asyncio.wait_for(graph.ainvoke(state), timeout=timeout)
    except TimeoutError:
        error_code = "timeout"
    except LLMError:
        error_code = "llm_failed"
    except UpstreamUnavailable:
        error_code = "upstream_unavailable"
    except Exception:  # noqa: BLE001 - retain failed-case evidence and continue the suite
        # Provider exception messages may contain sensitive configuration details.
        error_code = "internal_error"
    duration_ms = round((perf_counter() - started) * 1000, 2)
    if error_code:
        checks = {
            name: CheckResult(status="blocked", detail=f"Workflow failed: {error_code}")
            for name in CHECK_NAMES
        }
    else:
        # The current core has neither a card/link adapter nor HTTP SSE evidence.
        checks = evaluate_case(case, state)
    constraints = {
        key: value
        for key, value in case.filters.model_dump(exclude_none=True).items()
        if value is not False
    }
    candidates = {b.isbn13: b for b in state["candidates"]}
    shortlist = select_for_ranking(state["candidates"]) if not error_code else None
    rounds = state.get("ranking_rounds", []) if not error_code else None
    last_round = rounds[-1] if rounds else None
    return {
        "id": case.id,
        "query": case.query,
        "language": case.language,
        "category": case.category,
        "requested_filters": constraints,
        "unsupported_filters": sorted(constraints),
        "error_code": error_code,
        "workflow_duration_ms": duration_ms,
        "first_book_sse_ms": None,
        "retries": None if error_code else state["retries"],
        "searches_tried": None if error_code else state["tried"],
        "candidate_isbns": None if error_code else list(candidates),
        "parsed_query": (
            state["parsed"].model_dump() if not error_code and state["parsed"] else None
        ),
        "rankable_count": (
            None
            if error_code
            else sum(
                bool(b.description and b.description.strip())
                for b in state["candidates"]
            )
        ),
        "shortlist_isbns": (
            last_round["shortlist_isbns"]
            if last_round
            else None
            if shortlist is None
            else [b.isbn13 for b in shortlist]
        ),
        "ranking_input": (
            last_round["ranking_input"]
            if last_round
            else None
            if shortlist is None
            else format_candidates(shortlist)
        ),
        "model_calls": None if error_code else state.get("model_calls"),
        "ranking_rounds": rounds,
        "candidate_evidence": (
            None
            if error_code
            else [
                b.model_dump(
                    include={
                        "isbn13",
                        "title",
                        "authors",
                        "language",
                        "description",
                        "genres",
                        "source",
                        "page_count",
                        "published_year",
                    }
                )
                for b in state["candidates"]
            ]
        ),
        "recommendations": [
            {
                "isbn13": p.isbn13,
                "title": candidates[p.isbn13].title if p.isbn13 in candidates else None,
                "rank": p.rank,
                "reason": p.reason,
            }
            for p in state["picks"]
        ],
        "checks": {name: check.model_dump() for name, check in checks.items()},
    }


def summarize(results: list[dict]) -> dict:
    return {
        name: dict(Counter(result["checks"][name]["status"] for result in results))
        for name in CHECK_NAMES
    }


def save_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8"
    )
    temporary.replace(path)


async def run_live(suite_path: Path, output: Path, timeout: float) -> int:
    suite = load_suite(suite_path)
    settings = get_settings()
    model = create_chat_model()
    results = []
    report = {
        "report_version": 2,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "target": "recommendation_graph",
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "model": settings.llm_model,
        "revision": revision_info(),
        "code_sha256": code_fingerprints(),
        "expected_cases": len(suite.cases),
        "completed_cases": 0,
        "complete": False,
        "gate_passed": False,
        "capability_gaps": [
            "Book-card/store-link adapter is not implemented",
            "HTTP SSE first-book latency is not measured",
            "The graph does not yet apply request filter fields",
        ],
        "summary": {},
        "cases": results,
    }
    save_report(output, report)
    async with make_http_client() as client:
        graph = build_graph(model, client, settings.google_books_api_key)
        for number, case in enumerate(suite.cases, 1):
            result = await run_case(graph, case, timeout)
            results.append(result)
            report["completed_cases"] = len(results)
            report["summary"] = summarize(results)
            save_report(output, report)
            statuses = ", ".join(
                f"{name}={check['status']}" for name, check in result["checks"].items()
            )
            print(
                f"[{number}/{len(suite.cases)}] {case.id}: "
                f"{len(result['recommendations'])} picks, "
                f"{result['workflow_duration_ms'] / 1000:.2f}s; {statuses}",
                flush=True,
            )
    report["complete"] = True
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["gate_passed"] = gate_passed(results, {case.id for case in suite.cases})
    save_report(output, report)
    print(json.dumps(report["summary"], indent=2), flush=True)
    print(f"Report: {output.resolve()}", flush=True)
    print(
        f"Merge gate: {'PASS' if report['gate_passed'] else 'NOT PASSED'}", flush=True
    )
    return 0 if report["gate_passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--live", action="store_true", help="Run all 20 cases using configured services"
    )
    mode.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate suite coverage without service calls",
    )
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--timeout", type=float, default=60.0, help="Maximum seconds per query"
    )
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("Timeout must be finite and positive")
    try:
        suite = load_suite(args.suite)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.validate_only:
        print(
            f"Suite valid: {len(suite.cases)} cases, 10 English, 10 Spanish, 2 nonsense cases."
        )
        print("No recommendation checks or live calls were executed.")
        return 0
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output or DEFAULT_SUITE.parent / "results" / f"eval-{timestamp}.json"
    if output.exists():
        parser.error("The output file already exists; choose a new report path")
    return asyncio.run(run_live(args.suite, output, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())
