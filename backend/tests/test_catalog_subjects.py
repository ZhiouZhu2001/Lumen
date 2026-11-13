import httpx
import pytest

from app.filters import SearchFilters
from app.graph.search import search_candidates


@pytest.mark.parametrize(
    ("query", "subject"),
    [
        ("superhero moral dilemmas", "superheroes"),
        ("comics without superheroes", "comics"),
    ],
)
async def test_explicit_superhero_comics_use_the_specific_catalog_subject(
    query, subject
):
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: seen.append(request) or httpx.Response(200, json={})
        )
    ) as client:
        await search_candidates(
            client, [query], "en", filters=SearchFilters(genre="graphic novels")
        )
    assert len(seen) == 2
    assert all(f"subject:{subject}" in request.url.params["q"] for request in seen)


@pytest.mark.parametrize(
    ("genre", "subject"),
    [("adventure fiction", "fiction"), ("graphic novels", "comics")],
)
async def test_both_catalogs_receive_the_original_reading_form(genre, subject):
    seen = []

    def response(request):
        seen.append(request)
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        await search_candidates(
            client, ["journey exploration"], "en", filters=SearchFilters(genre=genre)
        )
    assert len(seen) == 2
    assert {request.url.host for request in seen} == {
        "www.googleapis.com",
        "openlibrary.org",
    }
    assert all(f"subject:{subject}" in request.url.params["q"] for request in seen)


@pytest.mark.parametrize("genre", ["popular science", "short stories", "nonfiction"])
async def test_nonfiction_and_collection_searches_keep_their_catalog_coverage(genre):
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: seen.append(request) or httpx.Response(200, json={})
        )
    ) as client:
        await search_candidates(
            client, ["subject:astronomy"], "es", filters=SearchFilters(genre=genre)
        )
    assert all("subject:fiction" not in request.url.params["q"] for request in seen)
    assert all("subject:astronomy" in request.url.params["q"] for request in seen)


async def test_manga_keeps_its_literal_form_without_a_restrictive_subject_label():
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: seen.append(request) or httpx.Response(200, json={})
        )
    ) as client:
        await search_candidates(
            client,
            ["manga aventuras equipo"],
            "es",
            filters=SearchFilters(genre="manga"),
        )
    assert len(seen) == 2
    assert all("manga aventuras equipo" in request.url.params["q"] for request in seen)
    assert all("subject:comics" not in request.url.params["q"] for request in seen)


async def test_broadened_manga_searches_keep_the_requested_form_word():
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: seen.append(request) or httpx.Response(200, json={})
        )
    ) as client:
        await search_candidates(
            client, ["aventuras equipo"], "es", filters=SearchFilters(genre="manga")
        )
    assert len(seen) == 2
    assert all("manga" in request.url.params["q"] for request in seen)


async def test_narrative_retrieval_uses_a_larger_pool_without_extra_requests():
    seen = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: seen.append(request) or httpx.Response(200, json={})
        )
    ) as client:
        await search_candidates(
            client,
            ["superhero comic"],
            "en",
            filters=SearchFilters(genre="graphic novels"),
        )
    assert len(seen) == 2
    google = next(
        request for request in seen if request.url.host == "www.googleapis.com"
    )
    assert google.url.params["maxResults"] == "40"


@pytest.mark.parametrize(
    ("query", "language", "expected"),
    [
        (
            "Graphic novels about superheroes",
            "en",
            ["ethics comics superhero", "superhero story"],
        ),
        (
            "Novelas gráficas sobre superhéroes",
            "es",
            ["ethics comics superhéroes", "superhero story"],
        ),
        ("Comics without superheroes", "en", ["ethics comics", "superhero story"]),
        ("Comics like superhero stories", "en", ["ethics comics", "superhero story"]),
    ],
)
def test_subgenre_search_anchor_preserves_the_literal_wish_and_exclusions(
    query, language, expected
):
    from app.reading_intent import anchor_subgenre_searches

    assert (
        anchor_subgenre_searches(query, ["ethics comics", "superhero story"], language)
        == expected
    )
