"""Measure real loopback HTTP SSE with private, in-process candidate evidence."""

import asyncio
import hashlib
import json
import socket
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.search import router
from app.config import get_settings
from app.filters import SearchFilters, matches_metadata
from app.main import lifespan
from app.observability import current_search_metrics
from app.usage import UsageUnavailable
from evals.checks import CHECK_NAMES, EvalLink, evaluate_case, gate_passed, load_suite
from evals.run import code_fingerprints, revision_info, run_case, save_report, summarize


@asynccontextmanager
async def evaluation_lifespan(app, *, hourly_namespace=None):
    async with lifespan(app):
        if hourly_namespace is not None:
            # Only Redis hourly admission is isolated. Preserve the original
            # DailyBudget object used by the API and outbound model transport.
            app.state.usage.namespace = hourly_namespace
        yield


async def budget_snapshot(budget):
    try:
        async with asyncio.timeout(2):
            return {"status": "known", **await budget.snapshot()}
    except (UsageUnavailable, OSError, TimeoutError):
        return {"status": "unknown"}


def budget_delta(before, after):
    if before.get("status") != "known" or after.get("status") != "known":
        return {"status": "unknown", "attempts": None}
    if before["utc_day"] != after["utc_day"]:
        return {"status": "utc_rollover", "attempts": None}
    difference = after["used"] - before["used"]
    if difference < 0:
        return {"status": "inconsistent", "attempts": None}
    return {"status": "same_utc_day", "attempts": difference}


async def run_http_live(
    suite_path,
    output,
    timeout,
    *,
    frontend_url=None,
    backend_port=0,
    isolate_hourly=False,
):
    suite = load_suite(suite_path)
    evidence = {}
    hourly_namespace = "lumen:eval:hourly:" + uuid4().hex if isolate_hourly else None

    @asynccontextmanager
    async def live_lifespan(app):
        async with evaluation_lifespan(app, hourly_namespace=hourly_namespace):
            yield

    app = FastAPI(lifespan=live_lifespan)
    app.include_router(router)
    app.include_router(health_router)

    def capture(search_id, state, cards, lookups, error_code):
        evidence[search_id] = (
            state,
            cards,
            lookups,
            error_code,
            current_search_metrics(),
        )

    app.state.search_observer = capture
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", backend_port))
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="error", access_log=False, proxy_headers=False)
    )
    task = asyncio.create_task(server.serve(sockets=[sock]))
    results = []
    report = {
        "report_version": 2,
        "runtime_evidence_version": 1,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "target": "frontend_http_sse_loopback" if frontend_url else "http_sse_loopback",
        "frontend_url": frontend_url,
        "backend_port": port,
        "suite_sha256": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
        "model": get_settings().llm_model,
        "daily_ai_call_cap": get_settings().daily_ai_call_cap,
        "usage_day_timezone": "UTC",
        "isolation": {
            "hourly_counter_isolated": isolate_hourly,
            "hourly_namespace": hourly_namespace,
            "daily_budget_shared": True,
            "cache_policy": "Existing shared caches retained; complete-result reuse measured per case; individual catalog-cache reuse is not fully tracked",
        },
        "budget_before": {"status": "not_checked"},
        "budget_after": {"status": "not_checked"},
        "revision": revision_info(),
        "code_sha256": code_fingerprints(),
        "expected_cases": 20,
        "completed_cases": 0,
        "complete": False,
        "gate_passed": False,
        "capability_gaps": [],
        "summary": {},
        "cases": results,
    }
    save_report(output, report)
    try:
        async with asyncio.timeout(15):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Evaluation HTTP server did not start")
                await asyncio.sleep(0.05)
        report["budget_before"] = await budget_snapshot(app.state.daily_budget)
        save_report(output, report)
        async with httpx.AsyncClient(
            base_url=frontend_url or f"http://127.0.0.1:{port}", timeout=timeout
        ) as client:
            for number, case in enumerate(suite.cases, 1):
                started = perf_counter()
                events = []
                first_ms = None
                first_event_ms = None
                content_encoding = None
                protocol_error = None
                http_status = None
                try:
                    async with asyncio.timeout(timeout):
                        async with client.stream(
                            "POST",
                            "/api/search",
                            headers={"Accept": "text/event-stream"},
                            json={
                                "query": case.query,
                                "language": case.language,
                                "filters": case.filters.model_dump(
                                    exclude_defaults=True
                                ),
                            },
                        ) as response:
                            http_status = response.status_code
                            response.raise_for_status()
                            content_encoding = response.headers.get("content-encoding")
                            if not response.headers.get("content-type", "").startswith(
                                "text/event-stream"
                            ):
                                raise ValueError("Not an SSE response")
                            event, data = "message", []
                            async for line in response.aiter_lines():
                                if line.startswith("event:"):
                                    event = line[6:].strip()
                                elif line.startswith("data:"):
                                    data.append(line[5:].lstrip())
                                elif not line and data:
                                    payload = json.loads("\n".join(data))
                                    if first_event_ms is None:
                                        first_event_ms = round(
                                            (perf_counter() - started) * 1000, 2
                                        )
                                    events.append({"event": event, "data": payload})
                                    if event == "book" and first_ms is None:
                                        first_ms = round(
                                            (perf_counter() - started) * 1000, 2
                                        )
                                    event, data = "message", []
                except (httpx.HTTPError, TimeoutError, ValueError):
                    protocol_error = "http_stream_failed"
                elapsed = round((perf_counter() - started) * 1000, 2)
                done = [e["data"] for e in events if e["event"] == "done"]
                captured = (
                    evidence.pop(done[-1]["search_id"], None)
                    if len(done) == 1
                    else None
                )
                if not captured:
                    result = {
                        "id": case.id,
                        "query": case.query,
                        "language": case.language,
                        "category": case.category,
                        "error_code": protocol_error or "missing_done_evidence",
                        "recommendations": [],
                        "checks": {
                            name: {
                                "status": "blocked",
                                "detail": "Incomplete HTTP SSE response",
                            }
                            for name in CHECK_NAMES
                        },
                    }
                else:
                    state, cards, lookups, error_code, metrics = captured

                    class CapturedGraph:
                        async def ainvoke(self, _, captured_state=state):
                            return captured_state

                    result = await run_case(CapturedGraph(), case, timeout)
                    links = {
                        card.isbn13: [
                            EvalLink(store=l.store, url=l.url) for l in card.links
                        ]
                        for card in cards
                    }
                    checks = evaluate_case(
                        case, state, links=links, first_book_sse_ms=first_ms
                    )
                    # Candidate count and the card payload must match actual wire events.
                    wire_cards = [e["data"] for e in events if e["event"] == "book"]
                    wire_valid = wire_cards == [
                        c.model_dump(mode="json") for c in cards
                    ] and done[-1]["total"] == len(cards)
                    filters = SearchFilters.model_validate(case.filters.model_dump())
                    metadata_ok = all(matches_metadata(c, filters) for c in cards)
                    result.update(
                        {
                            "error_code": protocol_error
                            or (
                                error_code
                                if error_code != "no_results"
                                or case.category != "nonsense"
                                else None
                            )
                            or (
                                None
                                if wire_valid and metadata_ok
                                else "wire_or_filter_mismatch"
                            ),
                            "unsupported_filters": [],
                            "workflow_duration_ms": None,
                            "http_duration_ms": elapsed,
                            "first_event_ms": first_event_ms,
                            "content_encoding": content_encoding,
                            "first_book_sse_ms": first_ms,
                            "cards": wire_cards,
                            "channel_lookups": lookups,
                            "runtime_usage": metrics,
                            "result_cache_hit": metrics["cache_hit"]
                            if metrics
                            else None,
                            "events": events,
                            "checks": {
                                name: c.model_dump() for name, c in checks.items()
                            },
                        }
                    )
                result["http_status"] = http_status
                result.setdefault("runtime_usage", None)
                result.setdefault("result_cache_hit", None)
                results.append(result)
                report["completed_cases"] = len(results)
                report["summary"] = summarize(results)
                report["budget_after"] = await budget_snapshot(app.state.daily_budget)
                report["budget_delta"] = budget_delta(
                    report["budget_before"], report["budget_after"]
                )
                save_report(output, report)
                statuses = ", ".join(
                    f"{name}={c['status']}" for name, c in result["checks"].items()
                )
                print(
                    f"[{number}/20] {case.id}: {len(result['recommendations'])} picks; first book={first_ms}ms; {statuses}",
                    flush=True,
                )
    finally:
        server.should_exit = True
        await task
        sock.close()
    report.update(
        complete=True,
        completed_at=datetime.now(UTC).isoformat(),
        gate_passed=gate_passed(results, {c.id for c in suite.cases}),
    )
    save_report(output, report)
    print(json.dumps(report["summary"], indent=2), flush=True)
    print(
        f"Merge gate: {'PASS' if report['gate_passed'] else 'NOT PASSED'}; report: {output}",
        flush=True,
    )
    return 0 if report["gate_passed"] else 1
