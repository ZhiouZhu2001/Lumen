"""Cache successful raw catalog JSON without changing normalization rules."""

import re
from datetime import UTC, datetime

import httpx
from pydantic import AwareDatetime, TypeAdapter

from app.search_cache import cache_key


class CatalogCacheTransport(httpx.AsyncBaseTransport):
    def __init__(self, cache, transport=None):
        self.cache = cache
        self.transport = transport or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request):
        url = request.url
        provider = None
        if (
            request.method == "GET"
            and url.scheme == "https"
            and url.port in (None, 443)
        ):
            if url.host == "www.googleapis.com" and url.path == "/books/v1/volumes":
                provider = "gbooks"
            elif url.host == "openlibrary.org" and (
                url.path == "/search.json"
                or re.fullmatch(r"/works/OL\d+W.json", url.path)
            ):
                provider = "olib"
        if provider is None:
            return await self.transport.handle_async_request(request)
        key = cache_key(f"lumen:catalog:v2:{provider}", str(url))
        cached = await self.cache.get(key)
        if (
            isinstance(cached, dict)
            and cached.get("url") == str(url)
            and isinstance(cached.get("payload"), dict)
        ):
            try:
                fetched = TypeAdapter(AwareDatetime).validate_python(
                    cached.get("fetched_at")
                )
                age = (datetime.now(UTC) - fetched).total_seconds()
                if 0 <= age < 86400:
                    return httpx.Response(
                        200,
                        json=cached["payload"],
                        extensions={"catalog_fetched_at": fetched},
                    )
            except ValueError:
                pass
        response = await self.transport.handle_async_request(request)
        if response.status_code == 200:
            await response.aread()
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    fetched = datetime.now(UTC)
                    response.extensions["catalog_fetched_at"] = fetched
                    await self.cache.put(
                        key,
                        {
                            "url": str(url),
                            "payload": payload,
                            "fetched_at": fetched.isoformat(),
                        },
                        24 * 3600,
                    )
            except ValueError:
                pass
        return response

    async def aclose(self):
        await self.transport.aclose()
