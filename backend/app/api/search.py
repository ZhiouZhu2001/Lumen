import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.sources.google_books import search_google_books
from app.sources.merge import merge_candidates
from app.sources.open_library import search_open_library
from app.sources.schemas import BookCandidate, Language

router = APIRouter(prefix="/api")


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    language: Language


class SearchResponse(BaseModel):
    books: list[BookCandidate]


@router.post("/search")
async def search(
    body: SearchRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SearchResponse:
    client = request.app.state.http

    # Ask both sources at the same time, then merge (Google wins).
    google, open_library = await asyncio.gather(
        search_google_books(
            client, body.query, body.language, api_key=settings.google_books_api_key
        ),
        search_open_library(client, body.query, body.language),
    )
    return SearchResponse(books=merge_candidates(google, open_library))
