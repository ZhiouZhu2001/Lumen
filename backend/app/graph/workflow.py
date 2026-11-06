import httpx
from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.broaden import broaden
from app.graph.parse_query import parse_query
from app.graph.rank import rank_and_explain
from app.graph.search import search_candidates
from app.graph.state import SearchState, route_after_search
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
        return {"parsed": parsed}

    async def search_node(state: SearchState):
        parsed = state["parsed"]

        if parsed is None:
            raise ValueError("Search requires a parsed query")

        tried = {search.casefold() for search in state["tried"]}
        searches = [
            search for search in parsed.searches if search.casefold() not in tried
        ]
        if not searches:
            return {}

        books = await search_candidates(
            client,
            searches,
            state["language"],
            google_api_key=google_api_key,
        )

        return {
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
        )
        return {"parsed": parsed, "retries": state["retries"] + 1}

    async def rank_node(state: SearchState):
        picks = await rank_and_explain(
            model,
            state["query"],
            state["language"],
            state["candidates"],
        )
        return {"picks": picks}

    builder = StateGraph(SearchState)

    builder.add_node("parse_query", parse_node)
    builder.add_node("search", search_node)
    builder.add_node("broaden", broaden_node)
    builder.add_node("rank_and_explain", rank_node)

    builder.add_edge(START, "parse_query")
    builder.add_edge("parse_query", "search")
    builder.add_conditional_edges("search", route_after_search)
    builder.add_edge("broaden", "search")
    builder.add_edge("rank_and_explain", END)

    return builder.compile()
