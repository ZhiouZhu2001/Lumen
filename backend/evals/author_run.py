"""Supplementary real HTTP author checks; never a replacement for the 20-case gate."""

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit

import httpx
import yaml

from app.authors import matches_authors
from app.channels.schemas import BookCard
from app.filters import SearchFilters, matches_metadata
from app.sources.isbn import to_isbn13
from evals.checks import EvalCase
from evals.run import code_fingerprints, revision_info, save_report

SUITE = Path(__file__).with_name("author_queries.yaml")


def check_cards(case: EvalCase, cards: list[BookCard], first_ms: float | None):
    minimum = 1 if case.category == "niche" else 5
    return {
        "count": minimum <= len(cards) <= 10,
        "requested_authors": bool(cards)
        and all(matches_authors(card, case.expected_authors) for card in cards),
        "metadata_filters": all(
            matches_metadata(
                card, SearchFilters.model_validate(case.filters.model_dump())
            )
            for card in cards
        ),
        "isbn_format": all(to_isbn13(card.isbn13) == card.isbn13 for card in cards),
        "first_book_latency": first_ms is not None and first_ms <= 15000,
    }


async def run(base_url: str, output: Path):
    data = yaml.safe_load(SUITE.read_text("utf-8"))
    cases = [EvalCase.model_validate(value) for value in data["cases"]]
    assert len(cases) == 2 and {case.language for case in cases} == {"en", "es"}
    assert all(case.expected_authors for case in cases)
    assert not output.exists()
    report = {
        "target": "supplementary_author_http_sse",
        "full_suite": False,
        "base_url": base_url,
        "started_at": datetime.now(UTC).isoformat(),
        "complete": False,
        "passed": False,
        "revision": revision_info(),
        "code_sha256": code_fingerprints(),
        "suite_sha256": hashlib.sha256(SUITE.read_bytes()).hexdigest(),
        "limitations": "Public wire checks do not independently capture candidate membership; the required 20-case private-observer gate remains separate.",
        "cases": [],
    }
    save_report(output, report)
    async with httpx.AsyncClient(base_url=base_url, timeout=60) as client:
        for case in cases:
            cards, errors, done = [], [], None
            first_ms = None
            event = "message"
            started = perf_counter()
            status = None
            try:
                async with client.stream(
                    "POST",
                    "/api/search",
                    headers={"Accept": "text/event-stream"},
                    json={
                        "query": case.query,
                        "language": case.language,
                        "filters": case.filters.model_dump(exclude_defaults=True),
                    },
                ) as response:
                    status = response.status_code
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:"):
                            payload = json.loads(line[5:])
                            if event == "book":
                                if first_ms is None:
                                    first_ms = round(
                                        (perf_counter() - started) * 1000, 2
                                    )
                                cards.append(BookCard.model_validate(payload))
                            elif event == "error":
                                errors.append(payload.get("code", "unknown"))
                            elif event == "done":
                                done = payload
            except (httpx.HTTPError, ValueError):
                errors.append("http_or_stream_failed")
            checks = check_cards(case, cards, first_ms)
            checks["completed_without_error"] = (
                not errors and done is not None and done.get("total") == len(cards)
            )
            report["cases"].append(
                {
                    "id": case.id,
                    "query": case.query,
                    "language": case.language,
                    "requested_filters": case.filters.model_dump(),
                    "expected_authors": case.expected_authors,
                    "status": status,
                    "cards": [card.model_dump(mode="json") for card in cards],
                    "first_book_ms": first_ms,
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                    "done": done,
                    "errors": errors,
                    "checks": checks,
                    "passed": all(checks.values()),
                }
            )
            save_report(output, report)
            print(f"{case.id}: {len(cards)} books; checks={checks}", flush=True)
    report["complete"] = True
    report["passed"] = all(case["passed"] for case in report["cases"])
    report["completed_at"] = datetime.now(UTC).isoformat()
    save_report(output, report)
    return 0 if report["passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if (
        url.scheme != "http"
        or url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in {"", "/"}
    ):
        parser.error("Use a loopback HTTP origin")
    return asyncio.run(run(args.base_url, args.output))


if __name__ == "__main__":
    raise SystemExit(main())
