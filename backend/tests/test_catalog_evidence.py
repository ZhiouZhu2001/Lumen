"""Original catalog objects survive normalization without becoming public data."""

from copy import deepcopy
from datetime import UTC, datetime

import httpx

from app.graph.rank import format_candidates
from app.search_cache import CompletedSearch
from app.sources.descriptions import enrich_descriptions
from app.sources.edition import parse_open_library_edition
from app.sources.evidence import mark_fetched, record
from app.sources.google_books import parse_google_books
from app.sources.merge import merge_candidates
from app.sources.open_library import parse_open_library
from tests.persistence_fixtures import completed
from tests.test_google_books import load


def test_original_google_object_is_an_independent_copy_and_never_serialized():
    payload = load("google_books_real_es.json")
    untouched = deepcopy(payload)
    book = parse_google_books(payload, "es")[0]
    original = book.provider_records["google_books"][0].payload
    assert original in untouched["items"]
    payload["items"].clear()
    assert original in untouched["items"]
    assert "provider_records" not in book.model_dump(mode="json")
    assert "volumeInfo" not in format_candidates([book])


def test_open_library_preserves_the_original_work_document_not_an_invented_edition():
    payload = load("open_library_edge_cases.json")
    book = parse_open_library(payload, "es")[0]
    original = book.provider_records["open_library_search"][0].payload
    assert original == payload["docs"][0]
    assert len(original["isbn"]) > 1
    assert original["isbn"] != [book.isbn13]


def test_merging_keeps_distinct_contributing_records_and_original_fetch_times():
    state, _ = completed(1)
    first = mark_fetched(state["candidates"][0], datetime(2026, 11, 1, tzinfo=UTC))
    later = first.model_copy(deep=True)
    later.description = None
    later.provider_records = {
        "google_books": [record({"id": "later-object"})],
        "open_library_search": [record({"key": "/works/OL1W"})],
    }
    merged = merge_candidates([first], [later])[0]
    again = merge_candidates([merged], [later])[0]
    assert len(merged.provider_records["google_books"]) == 2
    assert again.provider_records == merged.provider_records
    assert merged.catalog_fetched_at == first.catalog_fetched_at
    assert len(first.provider_records["google_books"]) == 1
    assert (
        merged.provider_records["google_books"][0].fetched_at
        == first.catalog_fetched_at
    )


def test_completed_cache_and_cards_exclude_original_objects():
    state, cards = completed(1)
    serialized = CompletedSearch(state=state, cards=cards).model_dump(mode="json")
    assert all("provider_records" not in b for b in serialized["state"]["candidates"])
    assert all("provider_records" not in b for b in serialized["cards"])
    restored = CompletedSearch.model_validate(serialized)
    assert not restored.state["candidates"][0].provider_records


async def test_description_enrichment_keeps_the_validated_work_response():
    book = parse_open_library(load("open_library_edge_cases.json"), "es")[0]
    book.work_key = "/works/OL1W"
    payload = {"key": book.work_key, "description": {"value": "Original work text."}}
    now = datetime.now(UTC)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json=payload, extensions={"catalog_fetched_at": now}
            )
        )
    ) as client:
        enriched = (await enrich_descriptions(client, [book]))[0]
    evidence = enriched.provider_records["open_library_work"][0]
    assert evidence.payload == payload and evidence.fetched_at == now
    assert enriched.description == "Original work text."
    assert "open_library_search" in enriched.provider_records
    assert "open_library_work" not in book.provider_records


def test_edition_response_is_retained_only_after_isbn_and_language_validation():
    payload = {
        "title": "Recorded edition",
        "isbn_13": ["9780307474728"],
        "languages": [{"key": "/languages/eng"}],
        "key": "/books/OL1M",
    }
    edition = parse_open_library_edition(payload, "9780307474728", "en")
    assert edition.provider_records["open_library_edition"][0].payload == payload
    assert parse_open_library_edition(payload, "9780307474728", "es") is None
    assert parse_open_library_edition(payload, "9780141439518", "en") is None
