"""Request-local timings and allowlisted application JSON logs, without payloads."""

import asyncio
import json
import logging
import math
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import wraps
from time import perf_counter
from uuid import UUID

EVENTS = {
    "search_started",
    "search_finished",
    "search_progress",
    "node_finished",
    "model_call_finished",
    "model_attempt_reserved",
    "search_storage_failed",
    "search_failed",
    "cache_write_unavailable",
    "redis_health_unavailable",
    "postgres_health_unavailable",
    "catalog_search_failed",
    "catalog_item_invalid",
    "unknown_candidate_rejected",
    "book_refresh_unavailable",
}
NODES = {"parse_query", "search", "broaden", "rank_and_explain"}
COUNTS = {"model_calls", "model_attempts", "book_count", "status_code"}
TIMINGS = {"duration_ms", "elapsed_ms"}
ERRORS = {"no_results", "rate_limited", "upstream_unavailable", "llm_failed"}


@dataclass
class SearchTrace:
    search_id: str
    cache_hit: bool = False
    started: float = field(default_factory=perf_counter)
    model_calls: int = 0
    model_attempts: int = 0
    book_count: int = 0
    outcome: str = "cancelled"
    error_code: str | None = None


@dataclass
class NodeTrace:
    name: str
    model_calls: int = 0
    model_attempts: int = 0


_search: ContextVar[SearchTrace | None] = ContextVar("lumen_search_trace", default=None)
_node: ContextVar[NodeTrace | None] = ContextVar("lumen_node_trace", default=None)
logger = logging.getLogger(__name__)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Never interpolate arguments, format exceptions or serialize arbitrary extras.
        data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": {
                10: "DEBUG",
                20: "INFO",
                30: "WARNING",
                40: "ERROR",
                50: "CRITICAL",
            }.get(record.levelno, "INFO"),
            "event": record.msg
            if isinstance(record.msg, str) and record.msg in EVENTS
            else "application_event",
        }
        search = _search.get()
        node = _node.get()
        identity = search.search_id if search else getattr(record, "search_id", None)
        if isinstance(identity, str):
            try:
                data["search_id"] = str(UUID(identity))
            except ValueError:
                pass
        name = node.name if node else getattr(record, "node", None)
        if isinstance(name, str) and name in NODES:
            data["node"] = name
        for key in COUNTS:
            value = getattr(record, key, None)
            if type(value) is int and value >= 0:
                data[key] = value
        for key in TIMINGS:
            value = getattr(record, key, None)
            if type(value) in (int, float) and math.isfinite(value) and value >= 0:
                data[key] = round(value, 3)
        outcome = getattr(record, "outcome", None)
        if isinstance(outcome, str) and outcome in {"completed", "failed", "cancelled"}:
            data["outcome"] = outcome
        code = getattr(record, "error_code", None)
        if isinstance(code, str) and code in ERRORS:
            data["error_code"] = code
        source = getattr(record, "source", None)
        if isinstance(source, str) and source in {"google_books", "open_library"}:
            data["source"] = source
        cache_hit = getattr(record, "cache_hit", None)
        if type(cache_hit) is bool:
            data["cache_hit"] = cache_hit
        return json.dumps(data, allow_nan=False, separators=(",", ":"))


class JsonHandler(logging.StreamHandler):
    def handleError(self, record):
        # A broken log sink must neither interrupt a search nor dump raw records.
        pass


def configure_logging():
    """Configure only application logging; do not enable third-party HTTP logs."""
    app_logger = logging.getLogger("app")
    handler = next(
        (item for item in app_logger.handlers if isinstance(item, JsonHandler)), None
    )
    for item in list(app_logger.handlers):
        if item is not handler:
            app_logger.removeHandler(item)
    if handler is None:
        handler = JsonHandler()
        handler.setFormatter(JsonFormatter())
        app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


@contextmanager
def bind_search(trace):
    token = _search.set(trace)
    try:
        yield
    finally:
        _search.reset(token)


def search_started(trace):
    with bind_search(trace):
        logger.info("search_started", extra={"cache_hit": trace.cache_hit})


def search_finished(trace):
    with bind_search(trace):
        logger.info(
            "search_finished",
            extra={
                "duration_ms": (perf_counter() - trace.started) * 1000,
                "model_calls": trace.model_calls,
                "model_attempts": trace.model_attempts,
                "book_count": trace.book_count,
                "cache_hit": trace.cache_hit,
                "outcome": trace.outcome,
                "error_code": trace.error_code,
            },
        )


@contextmanager
def model_call():
    trace = _search.get()
    node = _node.get()
    if trace is None:
        yield
        return
    trace.model_calls += 1
    if node is not None:
        node.model_calls += 1
    started = perf_counter()
    outcome = "cancelled"
    try:
        yield
        outcome = "completed"
    except Exception:
        outcome = "failed"
        raise
    finally:
        logger.info(
            "model_call_finished",
            extra={
                "duration_ms": (perf_counter() - started) * 1000,
                "outcome": outcome,
            },
        )


def model_attempt_reserved():
    """Called only after the real budget reservation commits, before HTTP send."""
    trace = _search.get()
    if trace is not None:
        trace.model_attempts += 1
        node = _node.get()
        if node is not None:
            node.model_attempts += 1
        logger.info(
            "model_attempt_reserved", extra={"model_attempts": trace.model_attempts}
        )


def instrument_node(name, run):
    @wraps(run)
    async def measured(state):
        if _search.get() is None:
            return await run(state)
        node = NodeTrace(name)
        token = _node.set(node)
        started = perf_counter()
        outcome = "cancelled"
        try:
            result = await run(state)
            outcome = "completed"
            return result
        except asyncio.CancelledError:
            raise
        except Exception:
            outcome = "failed"
            raise
        finally:
            logger.info(
                "node_finished",
                extra={
                    "duration_ms": (perf_counter() - started) * 1000,
                    "outcome": outcome,
                    "model_calls": node.model_calls,
                    "model_attempts": node.model_attempts,
                },
            )
            _node.reset(token)

    return measured
