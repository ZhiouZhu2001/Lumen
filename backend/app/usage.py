"""Atomic shared admission and provider-request budgets; Redis is mandatory."""

from ipaddress import ip_address, ip_network

import httpx
from redis.exceptions import RedisError


class UsageUnavailable(Exception):
    """A required safeguard could not be checked."""


class UsageLimited(Exception):
    def __init__(self, retry_after: int, *, daily: bool = False):
        self.retry_after = max(1, retry_after)
        self.daily = daily
        super().__init__("Daily AI limit reached" if daily else "Search limit reached")


# Redis time gives all workers the same clock. Rejected requests do not increment
# the counter, and IP keys never live longer than one hour after their creation.
COUNTER = """
local now = tonumber(redis.call('TIME')[1])
local window = tonumber(ARGV[1])
local bucket = math.floor(now / window)
local key = KEYS[1] .. ':' .. bucket
local remaining = (bucket + 1) * window - now
local used = tonumber(redis.call('GET', key) or '0')
if used >= tonumber(ARGV[2]) then return {0, remaining, used} end
if tonumber(ARGV[3]) == 1 then
  used = redis.call('INCR', key)
  if used == 1 then redis.call('EXPIRE', key, remaining) end
end
return {1, remaining, used}
"""


class UsageGuards:
    def __init__(self, redis, daily_cap: int, *, namespace: str = "lumen:usage:v1"):
        self.redis = redis
        self.daily_cap = daily_cap
        self.namespace = namespace

    async def _counter(self, scope: str, window: int, limit: int, consume: bool):
        try:
            allowed, retry, used = await self.redis.eval(
                COUNTER, 1, f"{self.namespace}:{scope}", window, limit, int(consume)
            )
        except (RedisError, OSError, TimeoutError) as error:
            raise UsageUnavailable(
                "Usage checks are temporarily unavailable"
            ) from error
        if not allowed:
            raise UsageLimited(int(retry), daily=scope == "ai")
        return int(used)

    async def admit_search(self, address: str):
        await self._counter("ip:" + address, 3600, 20, True)

    async def check_daily(self):
        await self._counter("ai", 86400, self.daily_cap, False)

    async def consume_ai(self):
        await self._counter("ai", 86400, self.daily_cap, True)


def client_address(peer: str, forwarded: str | None, trusted: list[str]) -> str:
    """Walk a validated proxy chain from the socket peer; ignore untrusted headers.

    Uvicorn must run with --no-proxy-headers so this boundary sees the real peer.
    """
    try:
        address = ip_address(peer)
        networks = [ip_network(value) for value in trusted]
        if any(address in network for network in networks) and forwarded:
            chain = [ip_address(value.strip()) for value in forwarded.split(",")]
            if len(chain) > 16:
                return str(address)
            for previous in reversed(chain):
                if not any(address in network for network in networks):
                    break
                address = previous
        return str(address)
    except ValueError:
        # A malformed forwarding chain never establishes a new identity.
        try:
            return str(ip_address(peer))
        except ValueError:
            return "unknown"


class BudgetTransport(httpx.AsyncBaseTransport):
    """Charge each actual model HTTP attempt, including SDK retries, before send."""

    def __init__(self, guards: UsageGuards, transport=None):
        self.guards = guards
        self.transport = transport or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        await self.guards.consume_ai()
        return await self.transport.handle_async_request(request)

    async def aclose(self):
        await self.transport.aclose()
