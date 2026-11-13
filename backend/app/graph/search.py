import asyncio
import logging
from collections.abc import Awaitable

import httpx

from app.filters import SearchFilters, catalog_subject
from app.sources.google_books import search_google_books
from app.sources.merge import merge_candidates
from app.sources.open_library import search_open_library
from app.sources.schemas import BookCandidate, Language

logger = logging.getLogger(__name__)


class UpstreamUnavailable(Exception):
    """Every source request failed (API error code: upstream_unavailable)."""


async def _try_source(
    name: str, search: Awaitable[list[BookCandidate]]
) -> list[BookCandidate] | None:
    """Run one source's search. Return None (and log why) if it fails."""
    try:
        return await search
    except (httpx.HTTPError, ValueError) as e:
        # httpx errors, or a response that isn't valid JSON (ValueError)
        logger.warning(
            "catalog_search_failed",
            extra={
                "source": {
                    "Google Books": "google_books",
                    "Open Library": "open_library",
                }.get(name),
                "status_code": getattr(
                    getattr(e, "response", None), "status_code", None
                ),
            },
        )
        return None


async def search_candidates(
    client: httpx.AsyncClient,
    searches: list[str],
    language: Language,
    google_api_key: str | None = None,
    *,
    filters: SearchFilters | None = None,
) -> list[BookCandidate]:
    """Run every search on both sources at once and merge the books by ISBN.
    Raise UpstreamUnavailable only if every single request failed.
    """
    if not searches:
        return []

    google_calls = [
        _try_source(
            "Google Books",
            search_google_books(
                client,
                search,
                language,
                api_key=google_api_key,
                **(
                    {"max_results": 40}
                    if filters and catalog_subject(filters.genre)
                    else {}
                ),
                **({"filters": filters} if filters else {}),
            ),
        )
        for search in searches
    ]

    open_library_calls = [
        _try_source(
            "Open Library",
            search_open_library(
                client, search, language, **({"filters": filters} if filters else {})
            ),
        )
        for search in searches
    ]

    results = await asyncio.gather(*google_calls, *open_library_calls)

    if all(result is None for result in results):
        raise UpstreamUnavailable("Google Books and Open Library both failed")

    # gather keeps the order: first the Google results, then Open Library
    google = [book for result in results[: len(searches)] for book in result or []]
    open_library = [
        book for result in results[len(searches) :] for book in result or []
    ]

    return merge_candidates(google, open_library)
