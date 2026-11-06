import httpx
from langchain_core.language_models import BaseChatModel
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.broaden import broaden
from app.graph.parse_query import parse_query
from app.graph.rank import (
    ModelPick,
    ModelPicks,
    RankingAttempt,
    format_candidates,
    rank_and_explain,
    validate_picks,
)
from app.graph.search import search_candidates
from app.graph.state import MAX_RETRIES, MIN_PICKS, SearchState, route_after_ranking
from app.llm import LLMError
from app.sources.merge import merge_candidates


def build_graph(
    model: BaseChatModel,
    client: httpx.AsyncClient,
    google_api_key: str | None = None,
) -> CompiledStateGraph:
    """Build the bounded recommendation flow using caller-owned resources."""

    async def parse_node(state: SearchState):
        parsed = await parse_query(
            model,
            state["query"],
            state["language"],
        )
        return {
            "parsed": parsed,
            "model_calls": 1,
            "feedback": [],
            "ranking_rounds": [],
            "picks": [],
            "request_understood": parsed.is_book_request,
        }

    async def search_node(state: SearchState):
        parsed = state["parsed"]

        if parsed is None:
            raise ValueError("Search requires a parsed query")

        tried = {search.casefold() for search in state["tried"]}
        searches = [
            search for search in parsed.searches if search.casefold() not in tried
        ]
        if not searches or not state.get("request_understood", True):
            return {"new_isbns": []}

        books = await search_candidates(
            client,
            searches,
            state["language"],
            google_api_key=google_api_key,
        )

        return {
            "new_isbns": [
                book.isbn13
                for book in books
                if book.isbn13 not in {b.isbn13 for b in state["candidates"]}
            ],
            "candidates": merge_candidates(
                state["candidates"],
                books,
            ),
            "tried": [*state["tried"], *searches],
        }

    async def broaden_node(state: SearchState):
        parsed = await broaden(
            model,
            state["query"],
            state["language"],
            state["tried"],
            feedback=state.get("feedback", []),
        )
        return {
            "parsed": parsed,
            "retries": state["retries"] + 1,
            "model_calls": state["model_calls"] + 1,
        }

    async def rank_node(state: SearchState):
        if state.get("request_understood", True):
            attempt = await rank_and_explain(
                model,
                state["query"],
                state["language"],
                state["candidates"],
                feedback=state.get("feedback", []),
                priority_isbns=[p.isbn13 for p in state["picks"]]
                + state.get("new_isbns", []),
            )
        else:
            attempt = RankingAttempt(
                [], ["Input has no meaningful reading intent"], [], [], False
            )
        combined = ModelPicks(
            picks=[
                ModelPick(isbn13=p.isbn13, reason=p.reason)
                for p in [*attempt.picks, *state["picks"]]
            ]
        )
        picks, _ = validate_picks(combined, state["candidates"], state["language"])
        if not picks and attempt.proposed and state["retries"] >= MAX_RETRIES:
            raise LLMError(
                "rank_and_explain returned no valid picks after bounded retries"
            )
        feedback = (
            [
                f"Only {len(picks)} validated matching recommendations; target {MIN_PICKS}-10. Find additional matching books without inventing facts.",
                *attempt.feedback,
            ]
            if len(picks) < MIN_PICKS
            else []
        )
        calls = state["model_calls"] + int(attempt.model_called)
        round_record = {
            "retry": state["retries"],
            "model_called": attempt.model_called,
            "shortlist_isbns": [b.isbn13 for b in attempt.shortlist],
            "ranking_input": format_candidates(attempt.shortlist),
            "proposed_picks": [p.model_dump() for p in attempt.proposed],
            "accepted_picks": [p.model_dump() for p in picks],
            "feedback": feedback,
            "validation_issues": attempt.feedback,
        }
        return {
            "picks": picks,
            "feedback": feedback,
            "model_calls": calls,
            "ranking_rounds": [*state["ranking_rounds"], round_record],
        }

    builder = StateGraph(SearchState)

    builder.add_node("parse_query", parse_node)
    builder.add_node("search", search_node)
    builder.add_node("broaden", broaden_node)
    builder.add_node("rank_and_explain", rank_node)

    builder.add_edge(START, "parse_query")
    builder.add_edge("parse_query", "search")
    builder.add_edge("search", "rank_and_explain")
    builder.add_conditional_edges("rank_and_explain", route_after_ranking)
    builder.add_edge("broaden", "search")

    return builder.compile()
