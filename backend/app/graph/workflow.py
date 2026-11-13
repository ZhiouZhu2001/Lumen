import httpx
from langchain_core.language_models import BaseChatModel
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.authors import (
    anchor_searches,
    clean_requested_authors,
    known_requested_authors,
    matches_authors,
)
from app.filters import (
    SearchFilters,
    catalog_subject,
    constrained_query,
    matches_metadata,
)
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
from app.grounding import description_evidence
from app.llm import LLMError
from app.observability import instrument_node
from app.reading_intent import anchor_subgenre_searches, matches_reader_type
from app.sources.descriptions import enrich_descriptions
from app.sources.merge import merge_candidates


def build_graph(
    model: BaseChatModel,
    client: httpx.AsyncClient,
    google_api_key: str | None = None,
    *,
    cache=None,
) -> CompiledStateGraph:
    """Build the bounded recommendation flow using caller-owned resources."""

    async def parse_node(state: SearchState):
        from app.graph.parse_query import ParsedQuery, clean_parsed_query

        query = constrained_query(state["query"], state.get("filters", SearchFilters()))
        key = cache.key("parse", [query, state["language"]]) if cache else None
        value = await cache.cache.get(key) if cache else None
        parsed = None
        if value is not None:
            try:
                parsed = clean_parsed_query(ParsedQuery.model_validate(value), query)
            except ValueError:
                pass
        model_called = parsed is None
        if parsed is None:
            parsed = await parse_query(model, query, state["language"])
            if cache:
                await cache.cache.put(key, parsed.model_dump(mode="json"), 7 * 86400)
        return {
            "parsed": parsed,
            "model_calls": int(model_called),
            "feedback": [],
            "ranking_rounds": [],
            "picks": [],
            "request_understood": parsed.is_book_request,
            "request_genre": state.get("filters", SearchFilters()).genre
            or parsed.genre,
            "request_authors": clean_requested_authors(
                state["query"], parsed.requested_authors
            ),
        }

    async def search_node(state: SearchState):
        parsed = state["parsed"]

        if parsed is None:
            raise ValueError("Search requires a parsed query")

        tried = {search.casefold() for search in state["tried"]}
        authors = state.get("request_authors", [])
        searches = [
            search
            for search in anchor_subgenre_searches(
                state["query"],
                anchor_searches(parsed.searches, authors),
                state["language"],
            )
            if search.casefold() not in tried
        ]
        if not searches or not state.get("request_understood", True):
            return {"new_isbns": []}

        filters = state.get("filters", SearchFilters())
        constrained = bool(filters.era or filters.length)
        source_filters = filters.model_copy(
            update={"genre": state.get("request_genre") or filters.genre}
        )
        books = await search_candidates(
            client,
            searches,
            state["language"],
            google_api_key=google_api_key,
            **(
                {"filters": source_filters}
                if constrained or source_filters.genre
                else {}
            ),
        )

        merged = merge_candidates(state["candidates"], books)
        authors = authors or known_requested_authors(state["query"], merged)
        attempted = list(state.get("description_lookup_keys", []))
        eligible = [
            b
            for b in merged
            if matches_metadata(b, filters)
            and matches_authors(b, authors)
            and matches_reader_type(
                b,
                state["query"],
                state.get("request_genre"),
                allow_missing_description=True,
            )
        ]
        graphic_retry = (
            state["retries"] > 0
            and len(state["picks"]) < MIN_PICKS
            and (
                catalog_subject(source_filters.genre) == "comics"
                or "manga" in (source_filters.genre or "").casefold().split()
            )
        )
        if constrained or graphic_retry:
            missing = []
            round_limit = 8 if constrained else 3
            # Spend bounded work lookups on already supported form/topic first.
            enrichment_order = (
                sorted(
                    eligible,
                    key=lambda b: (
                        not matches_reader_type(
                            b, state["query"], state.get("request_genre")
                        ),
                        catalog_subject(" ".join(b.genres)) != "comics",
                    ),
                )
                if graphic_retry
                else eligible
            )
            for book in enrichment_order:
                if (
                    book.work_key
                    and not description_evidence(book.description)
                    and book.work_key not in attempted
                ):
                    if len(attempted) >= 8 or len(missing) >= round_limit:
                        break
                    attempted.append(book.work_key)
                    missing.append(book)
            enriched = await enrich_descriptions(client, missing)
            verified = {
                b.work_key: b for b in enriched if description_evidence(b.description)
            }
            merged = [
                b.model_copy(
                    update={
                        "description": verified[b.work_key].description,
                        "catalog_fetched_at": min(
                            (
                                value
                                for value in (
                                    b.catalog_fetched_at,
                                    verified[b.work_key].catalog_fetched_at,
                                )
                                if value is not None
                            ),
                            default=None,
                        ),
                        "provider_records": {
                            **b.provider_records,
                            "open_library_work": verified[b.work_key].provider_records[
                                "open_library_work"
                            ],
                        },
                    }
                )
                if b.work_key in verified and not description_evidence(b.description)
                else b
                for b in merged
            ]

        return {
            "new_isbns": [
                book.isbn13
                for book in books
                if book.isbn13 not in {b.isbn13 for b in state["candidates"]}
            ],
            "candidates": merged,
            "description_lookup_keys": attempted,
            "tried": [*state["tried"], *searches],
            "request_authors": authors,
        }

    async def broaden_node(state: SearchState):
        selected = {p.isbn13 for p in state["picks"]}
        # Reuse real matching-book metadata, never unsupported names from reasons.
        authors = list(
            dict.fromkeys(
                author
                for b in state["candidates"]
                if b.isbn13 in selected
                for author in b.authors
                if author.strip()
            )
        )[:5]
        parsed = await broaden(
            model,
            constrained_query(state["query"], state.get("filters", SearchFilters())),
            state["language"],
            state["tried"],
            feedback=state.get("feedback", []),
            verified_authors=authors,
        )
        return {
            "parsed": parsed,
            "retries": state["retries"] + 1,
            "model_calls": state["model_calls"] + 1,
        }

    async def rank_node(state: SearchState):
        mismatches = set(state.get("reader_mismatch_isbns", []))
        eligible = [
            b
            for b in state["candidates"]
            if matches_metadata(b, state.get("filters", SearchFilters()))
            and matches_authors(b, state.get("request_authors", []))
            and b.isbn13 not in mismatches
            and matches_reader_type(b, state["query"], state.get("request_genre"))
        ]
        if state.get("request_understood", True):
            attempt = await rank_and_explain(
                model,
                constrained_query(
                    state["query"], state.get("filters", SearchFilters())
                ),
                state["language"],
                eligible,
                feedback=state.get("feedback", []),
                priority_isbns=[p.isbn13 for p in state["picks"]]
                + state.get("new_isbns", []),
                retained_picks=state["picks"],
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
        mismatches.update(
            issue.split(":", 1)[0]
            for issue in attempt.feedback
            if ": reason concedes a missing reader requirement" in issue
        )
        picks, _ = validate_picks(
            combined,
            [b for b in eligible if b.isbn13 not in mismatches],
            state["language"],
            query=state["query"],
            requested_authors=state.get("request_authors", []),
            requested_genre=state.get("request_genre"),
        )
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
            "reader_mismatch_isbns": sorted(mismatches),
        }

    builder = StateGraph(SearchState)

    builder.add_node("parse_query", instrument_node("parse_query", parse_node))
    builder.add_node("search", instrument_node("search", search_node))
    builder.add_node("broaden", instrument_node("broaden", broaden_node))
    builder.add_node("rank_and_explain", instrument_node("rank_and_explain", rank_node))

    builder.add_edge(START, "parse_query")
    builder.add_edge("parse_query", "search")
    builder.add_edge("search", "rank_and_explain")
    builder.add_conditional_edges("rank_and_explain", route_after_ranking)
    builder.add_edge("broaden", "search")

    return builder.compile()
