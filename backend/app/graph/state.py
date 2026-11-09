from typing import Literal, NotRequired, TypedDict

from langgraph.graph import END

from app.filters import SearchFilters
from app.graph.parse_query import ParsedQuery
from app.graph.rank import Pick
from app.sources.schemas import BookCandidate, Language

MAX_RETRIES = 2  # spec: broaden at most twice
MIN_PICKS = 5  # Approved flow: stop only after validating enough recommendations.


class SearchState(TypedDict):
    query: str
    language: Language
    parsed: ParsedQuery | None  # the latest searches, from parse_query or broaden
    tried: list[str]  # every search run so far
    candidates: list[BookCandidate]  # all books found so far, merged by ISBN
    retries: int
    picks: list[Pick]
    feedback: NotRequired[list[str]]
    new_isbns: NotRequired[list[str]]
    model_calls: NotRequired[int]
    ranking_rounds: NotRequired[list[dict]]
    request_understood: NotRequired[bool]
    filters: NotRequired[SearchFilters]
    description_lookup_keys: NotRequired[list[str]]
    request_genre: NotRequired[str | None]
    reader_mismatch_isbns: NotRequired[list[str]]
    request_authors: NotRequired[list[str]]


def route_after_ranking(
    state: SearchState,
) -> Literal["broaden", "__end__"]:
    """The graph's only branch: enough validated recommendations?"""
    if not state.get("request_understood", True):
        return END
    if len(state["picks"]) >= MIN_PICKS:
        return END
    if state["retries"] < MAX_RETRIES:
        return "broaden"
    return END  # Exhausted: preserve the valid subset, or report no_results.
