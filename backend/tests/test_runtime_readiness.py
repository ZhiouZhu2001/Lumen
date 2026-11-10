import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from scripts import check_runtime_readiness as module


@pytest.mark.parametrize(
    "state,code", [("ready", 0), ("not_ready", 1), ("cached_only", 2)]
)
def test_cli_preserves_distinct_operator_exit_states(monkeypatch, capsys, state, code):
    monkeypatch.setattr(module, "get_settings", lambda: None)
    monkeypatch.setattr(module, "run_check", AsyncMock(return_value={"state": state}))
    assert module.main() == code
    assert json.loads(capsys.readouterr().out)["state"] == state


def test_invalid_configuration_does_not_print_credential_bearing_error(
    monkeypatch, capsys
):
    error = ValidationError.from_exception_data(
        "Settings",
        [
            {
                "type": "int_parsing",
                "loc": ("daily_ai_call_cap",),
                "input": "private-credential-bearing-input",
            }
        ],
    )

    def invalid():
        raise error

    monkeypatch.setattr(module, "get_settings", invalid)
    assert module.main() == 1
    output = capsys.readouterr().out
    assert "private-credential-bearing-input" not in output
    assert json.loads(output)["error_kind"] == "ValidationError"


async def test_slow_redis_check_is_bounded_and_cancelled(monkeypatch):
    cancelled = []

    async def slow():
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    monkeypatch.setattr(module, "TIMEOUT_SECONDS", 0.01)
    assert await module.redis_status(SimpleNamespace(ping=slow)) == {
        "status": "unavailable"
    }
    assert cancelled == [True]


async def test_owned_resources_close_when_redis_creation_fails(monkeypatch):
    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(module, "expected_heads", lambda: ["head"])
    monkeypatch.setattr(module, "make_engine", lambda *_: engine)

    def invalid(*_):
        raise ValueError("private-redis-url")

    monkeypatch.setattr(module, "make_redis", invalid)
    with pytest.raises(ValueError):
        await module.run_check(SimpleNamespace(database_url="test", redis_url="test"))
    engine.dispose.assert_awaited_once()


async def test_engine_closes_even_when_redis_cleanup_fails(monkeypatch):
    engine = SimpleNamespace(dispose=AsyncMock())
    redis = SimpleNamespace(
        aclose=AsyncMock(side_effect=OSError("private-cleanup-error"))
    )
    monkeypatch.setattr(module, "expected_heads", lambda: ["head"])
    monkeypatch.setattr(module, "make_engine", lambda *_: engine)
    monkeypatch.setattr(module, "make_redis", lambda *_: redis)
    monkeypatch.setattr(
        module, "inspect_runtime", AsyncMock(return_value={"state": "ready"})
    )
    with pytest.raises(OSError):
        await module.run_check(SimpleNamespace(database_url="test", redis_url="test"))
    redis.aclose.assert_awaited_once()
    engine.dispose.assert_awaited_once()
