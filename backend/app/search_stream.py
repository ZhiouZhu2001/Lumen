"""Stream bounded graph progress and validated cards without exposing audit data."""

import asyncio
import json
import logging
from collections.abc import Callable
from time import perf_counter
from uuid import uuid4

from app.book_cards import BookCardBuilder
from app.filters import SearchFilters
from app.graph.search import UpstreamUnavailable
from app.graph.state import SearchState
from app.llm import LLMError
from app.sources.schemas import Language

logger = logging.getLogger(__name__)


def encode_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class SearchStream:
    def __init__(
        self, graph, cards: BookCardBuilder, *, observer: Callable | None = None
    ):
        self.graph = graph
        self.cards = cards
        # Local evaluator hook, never an HTTP endpoint or response payload.
        self.observer = observer

    async def events(self, query: str, language: Language, filters: SearchFilters):
        search_id = str(uuid4())
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
                async for update in self.graph.astream(state, stream_mode="updates"):
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
                if not state["picks"]:
                    error_code = "no_results"
                    yield encode_event(
                        "error", {"code": error_code, "message": messages[error_code]}
                    )
                else:
                    # Finish the first card before looking up later books, so a
                    # rate-limited optional retailer cannot hold the first book.
                    for pick in state["picks"]:
                        book = next(
                            b for b in state["candidates"] if b.isbn13 == pick.isbn13
                        )
                        batch = await self.cards.build(
                            [book], [pick.model_copy(update={"rank": 1})]
                        )
                        card = batch.cards[0].model_copy(update={"rank": pick.rank})
                        emitted.append(card)
                        lookups.update(batch.lookups)
                        yield encode_event("book", card.model_dump(mode="json"))
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
        yield encode_event(
            "done",
            {
                "search_id": search_id,
                "total": len(emitted),
                "limited": 0 < len(emitted) < 5 and not error_code,
            },
        )
