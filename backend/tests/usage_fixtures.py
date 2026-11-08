"""Explicit offline replacements for mandatory application dependencies."""

from unittest.mock import AsyncMock


class MemoryCache:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    async def get(self, key):
        return self.values.get(key)

    async def put(self, key, value, ttl):
        self.values[key] = value
        self.ttls[key] = ttl

    async def delete(self, key):
        self.values.pop(key, None)


def allow_searches(app):
    app.state.usage = type(
        "Usage",
        (),
        {
            "admit_search": AsyncMock(),
            "check_daily": AsyncMock(),
        },
    )()
    app.state.search_cache = type(
        "Cache",
        (),
        {"get_completed": AsyncMock(return_value=None), "put_completed": AsyncMock()},
    )()
    app.state.repository = None
