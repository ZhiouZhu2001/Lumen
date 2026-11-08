import re
from urllib.parse import urlsplit

import httpx

from app.channels.matching import matches_work, safe_url
from app.channels.schemas import BookLink
from app.sources.schemas import BookCandidate

SEARCH_URL = "https://itunes.apple.com/search"


def parse_apple_books(data: dict, book: BookCandidate) -> BookLink | None:
    rows = data.get("results") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise TypeError("Apple Books response has no results list")
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") != "ebook":
            continue
        title, author, raw_url = (
            row.get("trackName"),
            row.get("artistName"),
            row.get("trackViewUrl"),
        )
        if not all(
            isinstance(value, str) and value for value in (title, author, raw_url)
        ):
            continue
        url = safe_url(raw_url, "books.apple.com")
        identifier = row.get("trackId")
        if (
            url
            and urlsplit(url).path.startswith("/es/book/")
            and type(identifier) is int
            and identifier > 0
            and re.search(rf"/id{identifier}$", urlsplit(url).path)
            and matches_work(book, title, [author])
        ):
            return BookLink(
                store="apple_books",
                label="Apple Books",
                url=url,
                formats=["apple_books"],
                match="title_author",
            )
    return None


async def lookup_apple_books(
    client: httpx.AsyncClient, book: BookCandidate
) -> BookLink | None:
    authors = [name for name in book.authors if name.strip()]
    if not authors:
        return None
    response = await client.get(
        SEARCH_URL,
        params={
            "term": (book.title + " " + authors[0])[:240],
            "country": "ES",
            "media": "ebook",
            "entity": "ebook",
            "limit": 10,
        },
        timeout=4.0,
    )
    response.raise_for_status()
    return parse_apple_books(response.json(), book)
