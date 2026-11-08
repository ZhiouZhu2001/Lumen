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
from app.usage import UsageLimited, UsageUnavailable, client_address

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
            create_chat_model(http_client=request.app.state.model_http),
            request.app.state.http,
            settings.google_books_api_key,
            cache=request.app.state.search_cache,
        ),
        request.app.state.book_cards,
        repository=request.app.state.repository,
        observer=getattr(request.app.state, "search_observer", None),
        cache=request.app.state.search_cache,
    )


@router.post("/search", response_model=None)
async def search(
    body: SearchRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SearchResponse | StreamingResponse:
    sse = "text/event-stream" in request.headers.get("accept", "")
    if not sse and body.filters.model_dump(exclude_defaults=True):
        raise HTTPException(
            status_code=422, detail="Filters require Accept: text/event-stream"
        )
    usage = request.app.state.usage
    try:
        await usage.admit_search(
            client_address(
                request.client.host if request.client else "unknown",
                request.headers.get("x-forwarded-for"),
                settings.trusted_proxy_ips,
            )
        )
        cached = None
        if sse:
            cached = await request.app.state.search_cache.get_completed(
                body.query,
                body.language,
                body.filters,
                request.app.state.repository,
            )
            if cached is None:
                await usage.check_daily()
    except UsageLimited as error:
        raise HTTPException(
            status_code=503 if error.daily else 429,
            detail={
                "code": "rate_limited",
                "message": "The daily AI limit has been reached. Please try again tomorrow."
                if error.daily
                else "Too many searches. Please try again later.",
            },
            headers={"Retry-After": str(error.retry_after)},
        ) from None
    except UsageUnavailable:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "upstream_unavailable",
                "message": "Usage checks are unavailable. Please try again.",
            },
        ) from None
    if sse:
        stream = (
            SearchStream(
                None,
                request.app.state.book_cards,
                repository=request.app.state.repository,
                cached=cached,
                observer=getattr(request.app.state, "search_observer", None),
            )
            if cached is not None
            else get_search_stream(request, settings)
        )
        return StreamingResponse(
            stream.events(body.query, body.language, body.filters),
            media_type="text/event-stream",
            # Compression proxies otherwise buffer small SSE frames until EOF.
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
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
