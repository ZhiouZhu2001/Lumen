from typing import Literal, TypedDict

from langgraph.graph import END

from app.graph.parse_query import ParsedQuery
from app.graph.rank import Pick, select_for_ranking
from app.sources.schemas import BookCandidate, Language

MAX_RETRIES = 2  # spec: broaden at most twice
MIN_CANDIDATES = 10  # rankable books needed so the model can pick 5 to 10


class SearchState(TypedDict):
    query: str
    language: Language
    parsed: ParsedQuery | None  # the latest searches, from parse_query or broaden
    tried: list[str]  # every search run so far
    candidates: list[BookCandidate]  # all books found so far, merged by ISBN
    retries: int
    picks: list[Pick]


def route_after_search(
    state: SearchState,
) -> Literal["rank_and_explain", "broaden", "__end__"]:
    """The graph's only branch: enough candidates?"""
    rankable = len(select_for_ranking(state["candidates"]))
    if rankable >= MIN_CANDIDATES:
        return "rank_and_explain"
    if state["retries"] < MAX_RETRIES:
        return "broaden"
    if rankable > 0:
        return "rank_and_explain"  # spec: fewer than 5 is fine, pick from those
    return END  # spec: still nothing after 2 retries -> no_results
