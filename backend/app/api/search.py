import asyncio
import logging
from collections.abc import Awaitable
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.sources.google_books import search_google_books
from app.sources.merge import merge_candidates
from app.sources.open_library import search_open_library
from app.sources.schemas import BookCandidate, Language

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    language: Language


class SearchResponse(BaseModel):
    books: list[BookCandidate]


async def _try_source(
    name: str, search: Awaitable[list[BookCandidate]]
) -> list[BookCandidate] | None:
    """Run one source's search. Return None (and log why) if it fails."""
    try:
        return await search
    except (httpx.HTTPError, ValueError) as e:
        # httpx errors, or a response that isn't valid JSON (ValueError)
        logger.warning("%s search failed: %s: %s", name, type(e).__name__, e)
        return None


@router.post("/search")
async def search(
    body: SearchRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SearchResponse:
    client = request.app.state.http

    # Ask both sources at the same time. One failing must not break the other.
    google, open_library = await asyncio.gather(
        _try_source(
            "Google Books",
            search_google_books(
                client,
                body.query,
                body.language,
                api_key=settings.google_books_api_key,
            ),
        ),
        _try_source(
            "Open Library", search_open_library(client, body.query, body.language)
        ),
    )

    if google is None and open_library is None:
        # spec section 7: error code upstream_unavailable
        raise HTTPException(
            status_code=503,
            detail={
                "code": "upstream_unavailable",
                "message": "Book sources are not responding. Please try again.",
            },
        )

    return SearchResponse(books=merge_candidates(google or [], open_library or []))
