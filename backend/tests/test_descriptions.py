import json
from pathlib import Path

import httpx
import pytest

from app.filters import SearchFilters
from app.sources.descriptions import enrich_descriptions
from app.sources.open_library import search_open_library
from tests.test_workflow import book

FIXTURE = json.loads(
    (
        Path(__file__).parent / "fixtures/open_library_work_description_live.json"
    ).read_text("utf-8")
)


@pytest.mark.parametrize("representation", ["object", "text"])
async def test_recorded_description_fills_only_description_and_keeps_identity(
    representation,
):
    payload = dict(FIXTURE)
    if representation == "text":
        payload["description"] = payload["description"]["value"]
    original = book(0, None).model_copy(update={"work_key": payload["key"]})

    def handler(request):
        assert request.url == f"https://openlibrary.org{payload['key']}.json"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        enriched = (await enrich_descriptions(client, [original]))[0]
    assert enriched.description == FIXTURE["description"]["value"]
    assert enriched.isbn13 == original.isbn13 and enriched.language == original.language
    assert original.description is None
    assert "work_key" not in enriched.model_dump()


@pytest.mark.parametrize(
    "failure", ["http", "timeout", "wrong_work", "missing", "malformed"]
)
async def test_unavailable_or_unverified_work_never_gets_an_invented_description(
    failure,
):
    original = book(0, None).model_copy(update={"work_key": FIXTURE["key"]})

    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("offline", request=request)
        if failure == "http":
            return httpx.Response(503)
        payload = dict(FIXTURE)
        if failure == "wrong_work":
            payload["key"] = "/works/OL1W"
        if failure == "missing":
            payload.pop("description")
        if failure == "malformed":
            payload["description"] = ["not text"]
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (await enrich_descriptions(client, [original]))[0].description is None


async def test_unsafe_work_path_or_existing_description_makes_no_request():
    books = [
        book(0).model_copy(update={"work_key": FIXTURE["key"]}),
        book(1, None).model_copy(update={"work_key": "//untrusted.test/path"}),
    ]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected request"))
    ) as client:
        assert await enrich_descriptions(client, books) == books


async def test_open_library_sends_real_metadata_constraints():
    def handler(request):
        q = request.url.params["q"]
        assert "language:eng" in q
        assert "first_publish_year:[2010 TO 2019]" in q
        assert "number_of_pages_median:[1 TO 200]" in q
        return httpx.Response(200, json={"docs": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (
            await search_open_library(
                client,
                "short stories Spain",
                "en",
                filters=SearchFilters(era="2010s", length="short"),
            )
            == []
        )
