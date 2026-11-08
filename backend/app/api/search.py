from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.filters import SearchFilters
from app.graph.search import UpstreamUnavailable, search_candidates
from app.graph.workflow import build_graph
from app.llm import create_chat_model
from app.search_stream import SearchStream
from app.sources.schemas import BookCandidate, Language

router = APIRouter(prefix="/api")


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    language: Language
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchResponse(BaseModel):
    books: list[BookCandidate]


def get_search_stream(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> SearchStream:
    return SearchStream(
        build_graph(
            create_chat_model(), request.app.state.http, settings.google_books_api_key
        ),
        request.app.state.book_cards,
        repository=request.app.state.repository,
        observer=getattr(request.app.state, "search_observer", None),
    )


@router.post("/search", response_model=None)
async def search(
    body: SearchRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SearchResponse | StreamingResponse:
    if "text/event-stream" in request.headers.get("accept", ""):
        stream = get_search_stream(request, settings)
        return StreamingResponse(
            stream.events(body.query, body.language, body.filters),
            media_type="text/event-stream",
            # Compression proxies otherwise buffer small SSE frames until EOF.
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )
    if body.filters.model_dump(exclude_defaults=True):
        raise HTTPException(
            status_code=422, detail="Filters require Accept: text/event-stream"
        )
    try:
        books = await search_candidates(
            request.app.state.http,
            [body.query],
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
