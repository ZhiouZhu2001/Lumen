from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app import diagnostics
from app.llm import create_chat_model
from app.usage import UsageUnavailable


def test_model_factory_rejects_an_unmetered_default_client():
    with pytest.raises(UsageUnavailable):
        create_chat_model(http_client=None)


async def test_diagnostic_model_closes_resources_without_building_a_model_when_unready(
    monkeypatch,
):
    engine = SimpleNamespace(dispose=AsyncMock())
    budget = SimpleNamespace(check_daily=AsyncMock(side_effect=UsageUnavailable()))
    monkeypatch.setattr(
        diagnostics,
        "get_settings",
        lambda: SimpleNamespace(database_url="test", daily_ai_call_cap=100),
    )
    monkeypatch.setattr(diagnostics, "make_engine", lambda _: engine)
    monkeypatch.setattr(diagnostics, "DailyBudget", lambda *_: budget)
    factory = Mock()
    monkeypatch.setattr(diagnostics, "create_chat_model", factory)
    with pytest.raises(UsageUnavailable):
        async with diagnostics.diagnostic_model():
            pytest.fail("Uninitialized budget yielded a model")
    factory.assert_not_called()
    engine.dispose.assert_awaited_once()


async def test_diagnostic_client_and_database_close_even_when_the_tool_fails(
    monkeypatch,
):
    engine = SimpleNamespace(dispose=AsyncMock())
    budget = SimpleNamespace(check_daily=AsyncMock(), consume_ai=AsyncMock())
    monkeypatch.setattr(
        diagnostics,
        "get_settings",
        lambda: SimpleNamespace(database_url="test", daily_ai_call_cap=100),
    )
    monkeypatch.setattr(diagnostics, "make_engine", lambda _: engine)
    monkeypatch.setattr(diagnostics, "DailyBudget", lambda *_: budget)
    clients = []
    monkeypatch.setattr(
        diagnostics,
        "create_chat_model",
        lambda *, http_client: clients.append(http_client) or object(),
    )
    with pytest.raises(RuntimeError):
        async with diagnostics.diagnostic_model():
            raise RuntimeError("Tool failure")
    assert len(clients) == 1 and clients[0].is_closed
    budget.check_daily.assert_awaited_once()
    engine.dispose.assert_awaited_once()
