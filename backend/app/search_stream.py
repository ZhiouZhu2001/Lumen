"""Stream bounded graph progress and validated cards without exposing audit data."""

import asyncio
import json
import logging
from collections.abc import Callable
from time import perf_counter
from uuid import UUID, uuid4

from app.book_cards import BookCardBuilder
from app.filters import SearchFilters
from app.graph.rank import ModelPick, ModelPicks, validate_picks
from app.graph.search import UpstreamUnavailable
from app.graph.state import SearchState
from app.llm import LLMError
from app.observability import SearchTrace, bind_search, search_finished, search_started
from app.repository import SearchRepository, StorageUnavailable
from app.search_cache import CompletedSearch, SearchCache
from app.sources.schemas import Language
from app.usage import UsageLimited, UsageUnavailable

logger = logging.getLogger(__name__)
FIRST_BOOK_TARGET_SECONDS = 15.0
FIRST_CARD_LOOKUP_SECONDS = 1.0


def encode_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class SearchStream:
    def __init__(
        self,
        graph,
        cards: BookCardBuilder,
        *,
        observer: Callable | None = None,
        repository: SearchRepository | None = None,
        cache: SearchCache | None = None,
        cached: CompletedSearch | None = None,
    ):
        self.graph = graph
        self.cards = cards
        # Local evaluator hook, never an HTTP endpoint or response payload.
        self.observer = observer
        self.repository = repository
        self.cache = cache
        self.cached = cached

    async def events(self, query: str, language: Language, filters: SearchFilters):
        trace = SearchTrace(str(uuid4()), cache_hit=self.cached is not None)
        stream = self._events(query, language, filters, trace)
        search_started(trace)
        try:
            while True:
                # Bind only while executing the iterator, never across a yield.
                # Closing or interleaving generators in another task stays safe.
                with bind_search(trace):
                    try:
                        frame = await anext(stream)
                    except StopAsyncIteration:
                        break
                yield frame
        except Exception:
            trace.outcome = "failed"
            raise
        finally:
            with bind_search(trace):
                try:
                    await stream.aclose()
                finally:
                    search_finished(trace)

    async def _events(self, query, language, filters, trace):
        search_id = trace.search_id
        started = perf_counter()
        state = SearchState(
            query=query,
            language=language,
            filters=filters,
            parsed=None,
            tried=[],
            candidates=[],
            retries=0,
            picks=[],
        )
        if self.cached is not None:
            state = self.cached.state.copy()
            state["model_calls"] = 0
        emitted = []
        lookups = {}
        error_code = None
        messages = {
            "no_results": "No matching books found. Try a broader request.",
            "upstream_unavailable": "Book sources are unavailable. Please try again.",
            "llm_failed": "Recommendations are unavailable. Please try again.",
        }
        try:
            async with asyncio.timeout(60):
                yield encode_event("status", {"stage": "parsing"})

                async def updates():
                    if self.cached is not None:
                        yield {"search": {"candidates": state["candidates"]}}
                    else:
                        async for item in self.graph.astream(
                            state, stream_mode="updates"
                        ):
                            yield item

                async for update in updates():
                    for node, values in update.items():
                        state.update(values)
                        logger.info(
                            "search_progress",
                            extra={
                                "search_id": search_id,
                                "node": node,
                                "elapsed_ms": round((perf_counter() - started) * 1000),
                                "model_calls": state.get("model_calls", 0),
                            },
                        )
                        if node in ("parse_query", "broaden"):
                            yield encode_event("status", {"stage": "searching"})
                        elif node == "search":
                            yield encode_event(
                                "candidates", {"count": len(state["candidates"])}
                            )
                            yield encode_event("status", {"stage": "ranking"})
                        elif (
                            node == "rank_and_explain"
                            and len(state["picks"]) < 5
                            and state["retries"] < 2
                        ):
                            yield encode_event("status", {"stage": "searching"})
                valid, _ = validate_picks(
                    ModelPicks(
                        picks=[
                            ModelPick(isbn13=p.isbn13, reason=p.reason)
                            for p in state["picks"]
                        ]
                    ),
                    state["candidates"],
                    language,
                    query=query,
                    requested_authors=state.get(
                        "request_authors",
                        state["parsed"].requested_authors if state["parsed"] else [],
                    ),
                    requested_genre=filters.genre or state.get("request_genre"),
                )
                if [p.isbn13 for p in valid] != [p.isbn13 for p in state["picks"]]:
                    raise LLMError("Completed graph returned invalid recommendations")
                if not state["picks"]:
                    error_code = "no_results"
                    yield encode_event(
                        "error", {"code": error_code, "message": messages[error_code]}
                    )
                else:
                    # Finish the first card before looking up later books, so a
                    # rate-limited optional retailer cannot hold the first book.
                    for pick in state["picks"]:
                        if self.cached is not None:
                            card = self.cached.cards[pick.rank - 1]
                            emitted.append(card)
                            trace.book_count = len(emitted)
                            yield encode_event("book", card.model_dump(mode="json"))
                            continue
                        book = next(
                            b for b in state["candidates"] if b.isbn13 == pick.isbn13
                        )
                        batch = await self.cards.build(
                            [book],
                            [pick.model_copy(update={"rank": 1})],
                            lookup_timeout=(
                                min(
                                    FIRST_CARD_LOOKUP_SECONDS,
                                    max(
                                        0.0,
                                        FIRST_BOOK_TARGET_SECONDS
                                        - (perf_counter() - started)
                                        - 0.25,
                                    ),
                                )
                                if not emitted
                                else None
                            ),
                        )
                        card = batch.cards[0].model_copy(update={"rank": pick.rank})
                        emitted.append(card)
                        trace.book_count = len(emitted)
                        lookups.update(batch.lookups)
                        yield encode_event("book", card.model_dump(mode="json"))
                if self.repository is not None:
                    options = (
                        {"refresh_books": False} if self.cached is not None else {}
                    )
                    await self.repository.save_completed(
                        UUID(search_id),
                        state,
                        emitted,
                        round((perf_counter() - started) * 1000),
                        **options,
                    )
                if self.cache is not None and self.cached is None:
                    await self.cache.put_completed(state, emitted)
        except (UsageLimited, UsageUnavailable) as error:
            error_code = (
                "rate_limited"
                if isinstance(error, UsageLimited)
                else "upstream_unavailable"
            )
            yield encode_event(
                "error",
                {
                    "code": error_code,
                    "message": "The daily AI limit has been reached. Please try again tomorrow."
                    if isinstance(error, UsageLimited)
                    else "Usage checks are unavailable. Please try again.",
                },
            )
        except StorageUnavailable:
            error_code = "upstream_unavailable"
            logger.error("search_storage_failed", extra={"search_id": search_id})
            yield encode_event(
                "error",
                {
                    "code": error_code,
                    "message": "Could not save the search. Please try again.",
                },
            )
        except (UpstreamUnavailable, LLMError, TimeoutError) as error:
            error_code = (
                "upstream_unavailable"
                if isinstance(error, UpstreamUnavailable)
                else "llm_failed"
            )
            yield encode_event(
                "error", {"code": error_code, "message": messages[error_code]}
            )
        except Exception:  # noqa: BLE001 - sanitize failures at the HTTP stream boundary
            # Exception text can include provider URLs or credentials.
            logger.error("search_failed", extra={"search_id": search_id})
            error_code = "llm_failed"
            yield encode_event(
                "error", {"code": error_code, "message": messages[error_code]}
            )
        if self.observer is not None:
            self.observer(search_id, state, emitted, lookups, error_code)
        trace.book_count = len(emitted)
        trace.error_code = error_code
        trace.outcome = (
            "failed" if error_code not in (None, "no_results") else "completed"
        )
        yield encode_event(
            "done",
            {
                "search_id": search_id,
                "total": len(emitted),
                "limited": 0 < len(emitted) < 5 and not error_code,
            },
        )
