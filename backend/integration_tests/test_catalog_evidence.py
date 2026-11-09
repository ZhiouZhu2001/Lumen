"""Candidate coverage, private original objects and transactional compatibility."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app.channels.schemas import BookLink
from app.models import Book, SearchResult
from app.sources.evidence import record
from integration_tests.test_persistence import counts
from tests.persistence_fixtures import completed


async def raw_for(engine, isbn):
    async with engine.connect() as connection:
        return await connection.scalar(select(Book.raw).where(Book.isbn13 == isbn))


async def test_all_candidates_keep_original_objects_but_only_picks_become_results(
    storage,
):
    repository, engine = storage
    state, cards = completed(1)
    await repository.save_completed(uuid4(), state, cards, 100)
    assert await counts(engine) == [len(state["candidates"]), 1, 1]
    for candidate in state["candidates"]:
        raw = await raw_for(engine, candidate.isbn13)
        expected = candidate.provider_records["google_books"][0].model_dump(mode="json")
        assert raw["provider_records"]["google_books"] == [expected]
        assert (
            "provider_records"
            not in (await repository.get_book(candidate.isbn13)).model_dump()
        )
        assert not {"query", "reason", "search_id", "ip"}.intersection(raw)
    async with engine.connect() as connection:
        assert (await connection.scalars(select(SearchResult.isbn13))).all() == [
            cards[0].isbn13
        ]


async def test_empty_candidate_search_does_not_invent_book_rows(storage):
    repository, engine = storage
    state, cards = completed(0)
    state["candidates"] = []
    await repository.save_completed(uuid4(), state, cards, 100)
    assert await counts(engine) == [0, 1, 0]


@pytest.mark.parametrize("defect", ["checksum", "language", "blank_title", "duplicate"])
async def test_invalid_undisplayed_candidate_rolls_back_the_whole_search(
    storage, defect
):
    repository, engine = storage
    state, cards = completed(1)
    candidate = state["candidates"][-1]
    if defect == "checksum":
        candidate.isbn13 = "9780141439519"
    elif defect == "language":
        candidate.language = "en"
    elif defect == "blank_title":
        candidate.title = "   "
    else:
        state["candidates"].append(deepcopy(candidate))
    with pytest.raises(ValueError):
        await repository.save_completed(uuid4(), state, cards, 100)
    assert await counts(engine) == [0, 0, 0]


async def test_cache_replay_cannot_clear_originals_or_refresh_any_candidate(storage):
    from app.search_cache import CompletedSearch

    repository, engine = storage
    state, cards = completed(1)
    await repository.save_completed(uuid4(), state, cards, 100)
    before = [await raw_for(engine, b.isbn13) for b in state["candidates"]]
    replay = CompletedSearch.model_validate(
        CompletedSearch(state=state, cards=cards).model_dump(mode="json")
    )
    await repository.save_completed(
        uuid4(), replay.state, replay.cards, 10, refresh_books=False
    )
    assert [await raw_for(engine, b.isbn13) for b in state["candidates"]] == before
    assert await counts(engine) == [len(state["candidates"]), 2, 2]


async def test_refresh_adds_edition_evidence_preserves_other_sources_and_legacy_rows(
    storage,
):
    from app.sources.edition import parse_open_library_edition

    repository, engine = storage
    state, cards = completed(1)
    await repository.save_completed(uuid4(), state, cards, 100)
    isbn = cards[0].isbn13
    before = await raw_for(engine, isbn)
    async with engine.begin() as connection:
        await connection.execute(
            update(Book)
            .where(Book.isbn13 == isbn)
            .values(fetched_at=datetime.now(UTC) - timedelta(days=31))
        )
    original = await repository.get_book(isbn)
    payload = {
        "title": original.title,
        "isbn_13": [isbn],
        "languages": [{"key": "/languages/spa"}],
        "key": "/books/OL1M",
    }
    incoming = parse_open_library_edition(payload, isbn, "es")
    incoming.catalog_fetched_at = datetime.now(UTC) - timedelta(seconds=1)
    await repository.refresh_book(original, incoming)
    after = await raw_for(engine, isbn)
    assert (
        after["provider_records"]["google_books"]
        == before["provider_records"]["google_books"]
    )
    assert after["provider_records"]["open_library_edition"][0]["payload"] == payload
    # Earlier snapshots without a provider-record envelope remain readable/updatable.
    async with engine.begin() as connection:
        await connection.execute(
            update(Book)
            .where(Book.isbn13 == isbn)
            .values(
                raw={"snapshot_version": 1, "source": "google_books", "links": []},
                fetched_at=datetime.now(UTC) - timedelta(days=31),
            )
        )
    await repository.refresh_book(await repository.get_book(isbn), incoming)
    assert set((await raw_for(engine, isbn))["provider_records"]) == {
        "open_library_edition"
    }


async def test_newer_search_replaces_same_provider_records_without_accumulating_history(
    storage,
):
    repository, engine = storage
    state, cards = completed(1)
    first = datetime.now(UTC) - timedelta(hours=2)
    state["candidates"][0].catalog_fetched_at = first
    await repository.save_completed(uuid4(), state, cards, 100)
    newer = deepcopy(state)
    newer["candidates"][0].catalog_fetched_at = first + timedelta(hours=1)
    newer["candidates"][0].provider_records = {"google_books": [record({"id": "new"})]}
    await repository.save_completed(uuid4(), newer, cards, 100)
    raw = await raw_for(engine, cards[0].isbn13)
    assert [r["payload"] for r in raw["provider_records"]["google_books"]] == [
        {"id": "new"}
    ]
    await repository.save_completed(uuid4(), state, cards, 100)
    assert await raw_for(engine, cards[0].isbn13) == raw


@pytest.mark.parametrize("changed_identity", [False, True])
async def test_undisplayed_book_keeps_optional_link_only_for_unchanged_identity(
    storage, changed_identity
):
    repository, engine = storage
    state, cards = completed(1)
    await repository.save_completed(uuid4(), state, cards, 100)
    isbn = cards[0].isbn13
    raw = await raw_for(engine, isbn)
    raw["links"].append(
        BookLink(
            store="apple_books",
            label="Apple Books",
            url="https://books.apple.com/es/book/example/id123",
            formats=["apple_books"],
            match="title_author",
        ).model_dump(mode="json")
    )
    async with engine.begin() as connection:
        await connection.execute(
            update(Book).where(Book.isbn13 == isbn).values(raw=raw)
        )
    state["picks"] = []
    if changed_identity:
        state["candidates"][0].title += " revised"
    await repository.save_completed(uuid4(), state, [], 100)
    details = await repository.get_book(isbn)
    assert (
        any(link.store == "apple_books" for link in details.links)
        is not changed_identity
    )
