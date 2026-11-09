from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError
from redis.exceptions import ConnectionError

from app.config import Settings
from app.graph.parse_query import ParsedQuery
from app.llm import ask_structured
from app.usage import (
    BudgetTransport,
    UsageGuards,
    UsageLimited,
    UsageUnavailable,
    client_address,
)


@pytest.mark.parametrize(
    ("peer", "header", "trusted", "expected"),
    [
        ("192.0.2.2", "198.51.100.7", [], "192.0.2.2"),
        ("127.0.0.1", "198.51.100.7", ["127.0.0.1"], "198.51.100.7"),
        ("127.0.0.1", "203.0.113.9,198.51.100.7", ["127.0.0.1"], "198.51.100.7"),
        (
            "127.0.0.1",
            "198.51.100.7,10.0.0.2",
            ["127.0.0.1", "10.0.0.0/24"],
            "198.51.100.7",
        ),
        ("127.0.0.1", "invalid", ["127.0.0.1"], "127.0.0.1"),
        ("::1", "2001:db8::1", ["::1"], "2001:db8::1"),
    ],
)
def test_only_trusted_proxy_chain_can_supply_identity(peer, header, trusted, expected):
    assert client_address(peer, header, trusted) == expected


def test_settings_require_positive_cap_and_explicit_proxy_networks():
    for change in [
        {"daily_ai_call_cap": 0},
        {"trusted_proxy_ips": ["0.0.0.0/0"]},
        {"trusted_proxy_ips": ["bad"]},
    ]:
        with pytest.raises(ValidationError):
            Settings(database_url="test", redis_url="test", **change)


async def test_usage_outage_fails_closed():
    redis = type(
        "Redis", (), {"eval": AsyncMock(side_effect=ConnectionError("private URL"))}
    )()
    guards = UsageGuards(redis, 100)
    with pytest.raises(UsageUnavailable):
        await guards.consume_ai()
    redis.eval.assert_not_awaited()
    with pytest.raises(UsageUnavailable):
        await guards.admit_search("192.0.2.1")
    redis.eval.assert_awaited_once()


async def test_budget_denial_prevents_any_outbound_attempt():
    calls = []
    guards = type(
        "Guards",
        (),
        {"consume_ai": AsyncMock(side_effect=UsageLimited(20, daily=True))},
    )()
    async with httpx.AsyncClient(
        transport=BudgetTransport(
            guards, httpx.MockTransport(lambda r: calls.append(r))
        )
    ) as client:
        with pytest.raises(UsageLimited):
            await client.post("https://api.openai.com/v1/chat/completions")
    assert calls == []


@pytest.mark.parametrize(
    "exception", [UsageLimited(20, daily=True), UsageUnavailable()]
)
async def test_sdk_wrapped_budget_failures_keep_their_meaning(exception):
    class Wrapped:
        async def ainvoke(self, *_):
            raise RuntimeError("SDK wrapper") from exception

    model = type("Model", (), {"with_structured_output": lambda *_: Wrapped()})()
    with pytest.raises(type(exception)):
        await ask_structured(model, ParsedQuery, "system", "wish")
