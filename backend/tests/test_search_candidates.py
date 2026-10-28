import httpx
import pytest

from app.graph.search import UpstreamUnavailable, search_candidates

GOOGLE = "www.googleapis.com"
OPEN_LIBRARY = "openlibrary.org"

A, B, C = "9788437604947", "9788401242267", "9789500712347"

# search -> (ISBNs Google Books finds, ISBNs Open Library finds)
CATALOG = {
    "novela mar": ([A], [A, B]),
    "novela naufragio": ([B], [C]),
}


def google_payload(isbns: list[str]) -> dict:
    return {
        "items": [
            {
                "volumeInfo": {
                    "title": f"Google {isbn}",
                    "language": "es",
                    "industryIdentifiers": [{"type": "ISBN_13", "identifier": isbn}],
                }
            }
            for isbn in isbns
        ]
    }


def open_library_payload(isbns: list[str]) -> dict:
    return {
        "docs": [
            {"title": f"Open Library {isbn}", "language": ["spa"], "isbn": [isbn]}
            for isbn in isbns
        ]
    }


def fake_catalog(seen: list, failing: set = frozenset()):
    """Answer each (host, search) from CATALOG. Pairs in `failing` answer 503."""

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        search = request.url.params["q"].removesuffix(" language:spa")
        seen.append((host, search))
        if (host, search) in failing:
            return httpx.Response(503)
        google_isbns, open_library_isbns = CATALOG[search]
        if host == GOOGLE:
            return httpx.Response(200, json=google_payload(google_isbns))
        return httpx.Response(200, json=open_library_payload(open_library_isbns))

    return handler


async def run(seen: list, failing: set = frozenset()) -> list:
    transport = httpx.MockTransport(fake_catalog(seen, failing))
    async with httpx.AsyncClient(transport=transport) as client:
        return await search_candidates(client, list(CATALOG), "es")


async def test_every_search_goes_to_both_sources() -> None:
    seen: list = []
    await run(seen)
    assert len(seen) == 4  # 2 searches x 2 sources, nothing asked twice
    assert set(seen) == {
        (GOOGLE, "novela mar"),
        (GOOGLE, "novela naufragio"),
        (OPEN_LIBRARY, "novela mar"),
        (OPEN_LIBRARY, "novela naufragio"),
    }


async def test_books_from_all_searches_are_merged_once_by_isbn() -> None:
    books = await run([])
    assert [(b.isbn13, b.source) for b in books] == [
        (A, "google_books+open_library"),
        (B, "google_books+open_library"),  # found by different searches
        (C, "open_library"),
    ]


async def test_failed_requests_are_skipped() -> None:
    books = await run([], failing={(GOOGLE, "novela naufragio")})
    assert [(b.isbn13, b.source) for b in books] == [
        (A, "google_books+open_library"),
        (B, "open_library"),  # Google's copy of B was lost, Open Library's kept
        (C, "open_library"),
    ]


async def test_all_requests_failing_raises_upstream_unavailable() -> None:
    everything = {(host, s) for host in (GOOGLE, OPEN_LIBRARY) for s in CATALOG}
    with pytest.raises(UpstreamUnavailable):
        await run([], failing=everything)
