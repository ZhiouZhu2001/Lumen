import json
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.api import search as api
from app.api.books import router as books_router
from app.book_cards import BookCardBuilder
from app.channels.rules import load_rules
from app.channels.schemas import BookCard
from app.config import Settings, get_settings
from app.filters import SearchFilters
from app.graph.parse_query import ParsedQuery
from app.graph.rank import Pick
from app.graph.state import SearchState
from app.models import Search
from app.sources.schemas import BookCandidate
from integration_tests.test_persistence import counts
from tests.persistence_fixtures import completed
from tests.test_persistence_stream import SnapshotGraph
from tests.test_search_stream import decode


async def test_all_twenty_recorded_searches_persist_with_real_foreign_keys(storage):
    repository, engine = storage
    path = (
        Path(__file__).parents[1]
        / "evals/results/eval-frontend-20261108-round10-final.json"
    )
    capture = json.loads(path.read_text("utf-8"))
    assert (
        capture["complete"] and capture["gate_passed"] and len(capture["cases"]) == 20
    )
    recommended = set()
    total = 0
    for record in capture["cases"]:
        cards = [BookCard.model_validate(c) for c in record["cards"]]
        wire = {c.isbn13: c for c in cards}
        candidates = []
        for evidence in record["candidate_evidence"]:
            # Wire cards retain covers/ratings omitted from candidate snapshots.
            # Check the common evidence before restoring those public fields.
            if evidence["isbn13"] in wire:
                card = wire[evidence["isbn13"]]
                assert all(
                    card.model_dump(mode="json")[key] == value
                    for key, value in evidence.items()
                )
                candidates.append(BookCandidate.model_validate(card.model_dump()))
            else:
                candidates.append(BookCandidate.model_validate(evidence))
        state = SearchState(
            query=record["query"],
            language=record["language"],
            filters=SearchFilters.model_validate(record["requested_filters"]),
            parsed=ParsedQuery.model_validate(record["parsed_query"]),
            tried=record["searches_tried"],
            candidates=candidates,
            retries=record["retries"],
            picks=[Pick.model_validate(p) for p in record["recommendations"]],
        )
        await repository.save_completed(
            uuid4(), state, cards, round(record["http_duration_ms"])
        )
        total += len(cards)
        recommended.update(wire)
    assert await counts(engine) == [len(recommended), 20, total]
    for isbn in recommended:
        assert (await repository.get_book(isbn)).isbn13 == isbn


async def test_http_wiring_commits_before_done_and_details_read(storage, monkeypatch):
    from tests.usage_fixtures import allow_searches

    repository, engine = storage
    state, _ = completed(1)
    app = FastAPI()
    allow_searches(app)
    app.include_router(api.router)
    app.include_router(books_router)
    app.state.repository = repository
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="postgresql+asyncpg://test", redis_url="redis://test"
    )
    app.state.model_http = None
    monkeypatch.setattr(api, "create_chat_model", lambda **kwargs: None)
    monkeypatch.setattr(
        api, "build_graph", lambda *args, **kwargs: SnapshotGraph(state)
    )
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: pytest.fail("Unexpected external API request")
        )
    ) as outgoing:
        app.state.http = outgoing
        app.state.book_cards = BookCardBuilder(
            outgoing, rules=[r for r in load_rules() if r.mode == "search"]
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/search",
                headers={"Accept": "text/event-stream"},
                json={"query": state["query"], "language": "es"},
            )
            events = decode(response.text)
            done = events[-1][1]
            details = await client.get("/api/books/" + state["picks"][0].isbn13)
    assert not any(event == "error" for event, _ in events)
    assert events[-1][0] == "done" and done["total"] == 1 and details.status_code == 200
    async with engine.connect() as c:
        assert (
            await c.execute(
                select(Search.id).where(Search.id == UUID(done["search_id"]))
            )
        ).scalar_one()
