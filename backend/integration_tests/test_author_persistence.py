from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models import Search
from integration_tests.test_persistence import counts
from tests.test_author_constraints import captured


async def test_wrong_author_snapshot_leaves_no_database_rows(storage):
    repository, engine = storage
    snapshot = captured()
    with pytest.raises(ValueError):
        await repository.save_completed(uuid4(), snapshot.state, snapshot.cards, 10)
    assert await counts(engine) == [0, 0, 0]


async def test_only_exact_author_is_recommended_while_all_candidates_are_cached(
    storage,
):
    repository, engine = storage
    snapshot = captured()
    cards = [c for c in snapshot.cards if c.isbn13 == "9788417346201"]
    snapshot.state["picks"] = [
        p for p in snapshot.state["picks"] if p.isbn13 == cards[0].isbn13
    ]
    snapshot.state["request_authors"] = ["Toine Heijmans"]
    await repository.save_completed(uuid4(), snapshot.state, cards, 10)
    assert await counts(engine) == [len(snapshot.state["candidates"]), 1, 1]
    book = await repository.get_book(cards[0].isbn13)
    assert book.authors == ["Toine Heijmans"]
    assert book.published_year == 2018 and book.page_count == 128
    async with engine.connect() as connection:
        parsed = await connection.scalar(select(Search.parsed_query))
    assert parsed["requested_authors"] == ["Toine Heijmans"]
