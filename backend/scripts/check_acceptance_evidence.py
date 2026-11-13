"""Audit retained HTTP acceptance evidence; never execute searches or deploy."""

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

from evals.checks import CHECK_NAMES, gate_passed, load_suite
from evals.replay import recheck_report
from evals.run import DEFAULT_SUITE, code_fingerprints, summarize

BACKEND = DEFAULT_SUITE.parent.parent


def matches_text_digest(raw: bytes, expected: str) -> bool:
    """Allow only the uniform LF/CRLF conversion used by Git text checkouts."""
    if not isinstance(expected, str):
        return False
    lf = raw.replace(b"\r\n", b"\n")
    return expected in {
        hashlib.sha256(value).hexdigest()
        for value in (raw, lf, lf.replace(b"\n", b"\r\n"))
    }


def integer(value, minimum=0, maximum=None):
    return (
        type(value) is int
        and value >= minimum
        and (maximum is None or value <= maximum)
    )


def finite_number(value):
    return type(value) in (float, int) and math.isfinite(value)


def outcome(issues, **evidence):
    return {
        "report_version": 1,
        "state": "not_verified" if issues else "verified",
        "issues": list(dict.fromkeys(issues)),
        "scope": "Retained local HTTP capture only; not a new live run, runtime check or public-release approval",
        "model_requests": 0,
        "catalog_requests": 0,
        "new_latency_measurements": False,
        **evidence,
    }


def _inspect_capture(report):
    if (
        not isinstance(report, dict)
        or report.get("report_version") != 2
        or report.get("runtime_evidence_version") != 1
        or report.get("complete") is not True
        or report.get("gate_passed") is not True
        or report.get("full_suite") is False
        or report.get("expected_cases") != 20
        or report.get("completed_cases") != 20
        or report.get("target")
        not in {"http_sse_loopback", "frontend_http_sse_loopback"}
    ):
        return outcome(["incomplete_or_non_http_gate"])
    suite = load_suite(DEFAULT_SUITE)
    expected = {case.id: case for case in suite.cases}
    cases = report["cases"]
    if (
        not isinstance(cases, list)
        or len(cases) != 20
        or not all(isinstance(case, dict) for case in cases)
        or {case["id"] for case in cases} != set(expected)
    ):
        return outcome(["case_set_mismatch"])
    issues = []
    if not isinstance(report.get("model"), str) or not report["model"].strip():
        issues.append("model_identity_missing")
    if not matches_text_digest(DEFAULT_SUITE.read_bytes(), report.get("suite_sha256")):
        issues.append("suite_changed")
    sources = code_fingerprints()
    captured = report["code_sha256"]
    if not isinstance(captured, dict) or set(captured) != set(sources):
        return outcome([*issues, "source_inventory_mismatch"])
    line_endings = []
    for name in sources:
        raw = (BACKEND / name).read_bytes()
        if not matches_text_digest(raw, captured[name]):
            issues.append("source_changed")
        elif hashlib.sha256(raw).hexdigest() != captured[name]:
            line_endings.append(name)
    if issues:
        return outcome(issues)
    started = datetime.fromisoformat(report["started_at"])
    completed = datetime.fromisoformat(report["completed_at"])
    if not started.tzinfo or not completed.tzinfo or completed < started:
        issues.append("capture_time_invalid")
    if not gate_passed(cases, set(expected)):
        issues.append("declared_checks_not_passed")
    if report["summary"] != summarize(cases):
        issues.append("summary_mismatch")
    for case in cases:
        spec = expected[case["id"]]
        if any(
            case[key] != getattr(spec, key) for key in ("query", "language", "category")
        ):
            issues.append("case_metadata_mismatch")
        if case["requested_filters"] != spec.filters.model_dump(exclude_defaults=True):
            issues.append("case_filters_mismatch")
        if case["unsupported_filters"] != []:
            issues.append("unsupported_filter_evidence")
        cards, events = case["cards"], case["events"]
        delivered = [event["data"] for event in events if event["event"] == "book"]
        done = [event["data"] for event in events if event["event"] == "done"]
        errors = [event["data"] for event in events if event["event"] == "error"]
        if (
            case["http_status"] != 200
            or cards != delivered
            or len(done) != 1
            or done[0]["total"] != len(cards)
            or not events
            or events[-1]["event"] != "done"
            or case["recommendations"]
            != [
                {key: card[key] for key in ("isbn13", "rank", "reason")}
                for card in cards
            ]
            or (
                errors
                and not (
                    spec.category == "nonsense"
                    and not cards
                    and len(errors) == 1
                    and errors[0]["code"] == "no_results"
                )
            )
        ):
            issues.append("delivery_mismatch")
        first, duration = case["first_book_sse_ms"], case["http_duration_ms"]
        if not finite_number(duration) or duration < 0:
            issues.append("retained_latency_invalid")
        if spec.category == "nonsense":
            if (
                first is not None
                or case["checks"]["latency"]["status"] != "not_applicable"
            ):
                issues.append("retained_latency_invalid")
        elif not finite_number(first) or not 0 <= first <= 15000 or first > duration:
            issues.append("retained_latency_invalid")
        usage = case["runtime_usage"]
        if (
            not integer(case["retries"], maximum=2)
            or not integer(usage["model_calls"], maximum=6)
            or not integer(usage["model_attempts"], minimum=usage["model_calls"])
            or type(case["result_cache_hit"]) is not bool
            or usage["cache_hit"] is not case["result_cache_hit"]
            or (
                case["result_cache_hit"]
                and (usage["model_calls"] or usage["model_attempts"])
            )
        ):
            issues.append("runtime_usage_invalid")
    # Replay recomputes non-latency checks. Retained timing is checked above,
    # never presented as a new measurement from this file-only audit.
    replay = recheck_report(report, suite)
    if any(
        case["checks"][name]["status"] != "pass"
        for case in replay
        for name in CHECK_NAMES
        if name != "latency"
    ):
        issues.append("recomputed_checks_failed")
    before, after, delta = (
        report["budget_before"],
        report["budget_after"],
        report["budget_delta"],
    )
    attempts = sum(case["runtime_usage"]["model_attempts"] for case in cases)
    cap = report["daily_ai_call_cap"]
    if (
        report["usage_day_timezone"] != "UTC"
        or report["isolation"]["daily_budget_shared"] is not True
        or before["status"] != "known"
        or after["status"] != "known"
        or before["utc_day"] != after["utc_day"]
        or before["utc_day"] != started.astimezone(UTC).date().isoformat()
        or after["utc_day"] != completed.astimezone(UTC).date().isoformat()
        or not integer(cap, minimum=1)
        or before["daily_cap"] != cap
        or after["daily_cap"] != cap
        or not integer(before["used"])
        or not integer(after["used"], minimum=before["used"], maximum=cap)
        or after["used"] - before["used"] != attempts
        or delta != {"status": "same_utc_day", "attempts": attempts}
    ):
        issues.append("shared_budget_mismatch")
    if issues:
        return outcome(issues)
    return outcome(
        [],
        target=report["target"],
        captured_model_sha256=hashlib.sha256(report["model"].encode()).hexdigest(),
        current_runtime_configuration_checked=False,
        cases_checked=20,
        cards_checked=sum(len(case["cards"]) for case in cases),
        complete_result_cache_hits=sum(case["result_cache_hit"] for case in cases),
        observed_model_attempts=attempts,
        budget_before=before["used"],
        budget_after=after["used"],
        capture_daily_cap=cap,
        source_identity="Raw SHA-256 or uniform LF/CRLF equivalent only",
        line_ending_equivalent_sources=line_endings,
    )


def check_report(path: Path):
    try:
        raw = path.read_bytes()
        result = _inspect_capture(json.loads(raw))
        return {
            **result,
            "input_sha256": hashlib.sha256(raw).hexdigest(),
            "input_lf_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        }
    except (
        OSError,
        UnicodeError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ):
        # Neither raw payloads nor credential-bearing exception text is output.
        return outcome(["unreadable_or_invalid_evidence"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = check_report(args.report)
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        except OSError:
            result = outcome(["output_unavailable_or_already_exists"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["state"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
