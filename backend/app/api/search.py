from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.graph.search import UpstreamUnavailable, search_candidates
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
    try:
        books = await search_candidates(
            request.app.state.http,
            [body.query],  # for now: the reader's words. Next: parse_query's searches
            body.language,
            google_api_key=settings.google_books_api_key,
        )
    except UpstreamUnavailable:
        # spec section 7: error code upstream_unavailable
        raise HTTPException(
            status_code=503,
            detail={
                "code": "upstream_unavailable",
                "message": "Book sources are not responding. Please try again.",
            },
        ) from None

    return SearchResponse(books=books)
