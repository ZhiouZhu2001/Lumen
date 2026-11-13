"""Audit actual retained captures and inconsistent copies without live services."""

import copy
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from scripts import check_acceptance_evidence as audit

RESULTS = Path(__file__).parents[1] / "evals/results"
CAPTURE = RESULTS / "eval-live-20261113-round25-merge-gate.json"
RECORDED = json.loads(CAPTURE.read_text("utf-8"))


def inspect_copy(tmp_path, report):
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(report), "utf-8")
    before = path.read_bytes()
    result = audit.check_report(path)
    assert path.read_bytes() == before
    return result


def test_real_complete_capture_verifies_without_runtime_or_network(monkeypatch):
    from app import db
    from evals import run

    def forbidden(*args, **kwargs):
        pytest.fail("Offline audit attempted a live operation")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    monkeypatch.setattr(httpx.AsyncClient, "send", forbidden)
    monkeypatch.setattr(db, "make_engine", forbidden)
    monkeypatch.setattr(run, "get_settings", forbidden)
    monkeypatch.setattr(run, "create_chat_model", forbidden)
    before = CAPTURE.read_bytes()
    result = audit.check_report(CAPTURE)
    assert result["state"] == "verified" and result["issues"] == []
    assert result["cases_checked"] == 20 and result["cards_checked"] == 144
    assert result["observed_model_attempts"] == 44
    assert (
        result["input_lf_sha256"]
        == hashlib.sha256(before.replace(b"\r\n", b"\n")).hexdigest()
    )
    assert result["complete_result_cache_hits"] == 1
    assert (
        result["budget_before"],
        result["budget_after"],
        result["capture_daily_cap"],
    ) == (190, 234, 300)
    assert result["model_requests"] == result["catalog_requests"] == 0
    assert not result["new_latency_measurements"]
    assert not result["current_runtime_configuration_checked"]
    assert CAPTURE.read_bytes() == before


def replace(report, path, value):
    for key in path[:-1]:
        report = report[key]
    report[path[-1]] = value


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("complete",), False),
        (("gate_passed",), False),
        (("full_suite",), False),
        (("report_version",), 1),
        (("runtime_evidence_version",), None),
        (("expected_cases",), 19),
        (("completed_cases",), 19),
        (("target",), "graph_only"),
        (("completed_at",), None),
        (("model",), ""),
        (("suite_sha256",), "0" * 64),
        (("code_sha256", "app/config.py"), "0" * 64),
        (("cases", 0, "query"), "A different reader request"),
        (("cases", 0, "requested_filters"), {"free_only": True}),
        (("cases", 0, "unsupported_filters"), None),
        (("cases", 0, "http_status"), 503),
        (("cases", 0, "checks", "reason", "status"), "fail"),
        (("summary", "reason", "pass"), 19),
        (("cases", 0, "first_book_sse_ms"), 15000.01),
        (("cases", 0, "first_book_sse_ms"), float("nan")),
        (("cases", 0, "first_book_sse_ms"), True),
        (("cases", 0, "retries"), 3),
        (("cases", 0, "runtime_usage", "model_calls"), 7),
        (("cases", 0, "runtime_usage", "model_attempts"), 0),
        (("cases", 0, "result_cache_hit"), True),
        (("isolation", "daily_budget_shared"), False),
        (("budget_after", "used"), 235),
        (("budget_after", "utc_day"), "2026-11-14"),
        (("daily_ai_call_cap",), 100),
    ],
)
def test_inconsistent_copies_never_inherit_a_passing_gate(tmp_path, path, value):
    report = copy.deepcopy(RECORDED)
    replace(report, path, value)
    result = inspect_copy(tmp_path, report)
    assert result["state"] == "not_verified" and result["issues"]


@pytest.mark.parametrize(
    "mutation",
    ["missing_case", "duplicate_case", "missing_source", "missing_wire", "wrong_total"],
)
def test_incomplete_identity_or_delivery_is_rejected(tmp_path, mutation):
    report = copy.deepcopy(RECORDED)
    case = report["cases"][0]
    if mutation == "missing_case":
        report["cases"].pop()
    elif mutation == "duplicate_case":
        report["cases"][-1] = copy.deepcopy(case)
    elif mutation == "missing_source":
        report["code_sha256"].pop(next(iter(report["code_sha256"])))
    elif mutation == "missing_wire":
        case["events"].pop(
            next(
                i for i, event in enumerate(case["events"]) if event["event"] == "book"
            )
        )
    else:
        case["events"][-1]["data"]["total"] += 1
    assert inspect_copy(tmp_path, report)["state"] == "not_verified"


@pytest.mark.parametrize("change", ["reason", "count"])
def test_claimed_passes_are_recomputed_from_underlying_book_evidence(tmp_path, change):
    report = copy.deepcopy(RECORDED)
    case = report["cases"][0]
    if change == "reason":
        reason = "It explores ZygmuntNebulopolis. It fits your request."
        case["cards"][0]["reason"] = case["recommendations"][0]["reason"] = reason
        next(event for event in case["events"] if event["event"] == "book")["data"][
            "reason"
        ] = reason
    else:
        case["cards"] = case["cards"][:4]
        case["recommendations"] = case["recommendations"][:4]
        retained = {card["isbn13"] for card in case["cards"]}
        case["events"] = [
            event
            for event in case["events"]
            if event["event"] != "book" or event["data"]["isbn13"] in retained
        ]
        case["events"][-1]["data"]["total"] = 4
    result = inspect_copy(tmp_path, report)
    assert result["state"] == "not_verified"
    assert "recomputed_checks_failed" in result["issues"]


@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_actual_capture_identity_accepts_uniform_git_line_endings(tmp_path, ending):
    report = copy.deepcopy(RECORDED)
    for name in report["code_sha256"]:
        raw = (
            (audit.BACKEND / name)
            .read_bytes()
            .replace(b"\r\n", b"\n")
            .replace(b"\n", ending)
        )
        report["code_sha256"][name] = hashlib.sha256(raw).hexdigest()
    raw = (
        audit.DEFAULT_SUITE.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", ending)
    )
    report["suite_sha256"] = hashlib.sha256(raw).hexdigest()
    assert inspect_copy(tmp_path, report)["state"] == "verified"


@pytest.mark.parametrize(
    ("current", "captured", "expected"),
    [
        (b"one\ntwo\n", b"one\r\ntwo\r\n", True),
        (b"one \ntwo\n", b"one\ntwo\n", False),
        (b"one\nchanged\n", b"one\ntwo\n", False),
    ],
)
def test_line_ending_equivalence_never_allows_other_whitespace_or_code(
    current, captured, expected
):
    assert (
        audit.matches_text_digest(current, hashlib.sha256(captured).hexdigest())
        is expected
    )


@pytest.mark.parametrize(
    "name",
    [
        "eval-live-20261113-round25-final.json",
        "eval-supplementary-20261113-round25-comics-current.json",
    ],
)
def test_real_failed_or_supplementary_reports_are_not_complete_gates(name):
    assert audit.check_report(RESULTS / name)["state"] == "not_verified"


def test_cli_writes_new_audit_without_overwriting_evidence(tmp_path, capsys):
    output = tmp_path / "audit.json"
    args = ["--report", str(CAPTURE), "--output", str(output)]
    assert audit.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert json.loads(output.read_text("utf-8")) == result
    before = output.read_bytes()
    assert audit.main(args) == 1
    assert output.read_bytes() == before
    assert (
        "output_unavailable_or_already_exists"
        in json.loads(capsys.readouterr().out)["issues"]
    )
    before = CAPTURE.read_bytes()
    assert audit.main(["--report", str(CAPTURE), "--output", str(CAPTURE)]) == 1
    assert CAPTURE.read_bytes() == before


@pytest.mark.parametrize(
    "payload",
    [
        '{"private-credential":"not-json"',
        '{"report_version": 2, "private-credential":"private-value"}',
        "null",
    ],
)
def test_invalid_input_never_echoes_private_payloads(tmp_path, capsys, payload):
    path = tmp_path / "bad.json"
    path.write_text(payload, "utf-8")
    assert audit.main(["--report", str(path)]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["state"] == "not_verified"
    assert "private-credential" not in output and "private-value" not in output


def test_unreadable_input_fails_without_exception_text(tmp_path):
    assert audit.check_report(tmp_path / "absent.json")["state"] == "not_verified"
