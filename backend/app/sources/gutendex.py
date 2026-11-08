import re
from urllib.parse import urlsplit

import httpx

from app.channels.matching import matches_work, normalize, safe_url
from app.channels.schemas import BookLink
from app.sources.schemas import BookCandidate

SEARCH_URL = "https://gutendex.com/books/"


def parse_gutendex(data: dict, book: BookCandidate) -> BookLink | None:
    rows = data.get("results") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise TypeError("Gutendex response has no results list")
    for row in rows:
        if not isinstance(row, dict):
            continue
        identifier, title, authors = row.get("id"), row.get("title"), row.get("authors")
        languages, formats = row.get("languages"), row.get("formats")
        if (
            type(identifier) is not int
            or identifier < 1
            or not isinstance(title, str)
            or not isinstance(authors, list)
            or not isinstance(languages, list)
            or book.language not in languages
            or row.get("copyright") is not False
            or row.get("media_type") != "Text"
            or not isinstance(formats, dict)
        ):
            continue
        names = [
            a["name"]
            for a in authors
            if isinstance(a, dict) and isinstance(a.get("name"), str)
        ]
        if not matches_work(book, title, names):
            continue
        for mime in ("text/html", "application/epub+zip", "text/plain; charset=utf-8"):
            raw_url = formats.get(mime)
            url = (
                safe_url(raw_url, "gutenberg.org", upgrade_http=True)
                if isinstance(raw_url, str)
                else None
            )
            if url and re.search(
                rf"/(?:ebooks/{identifier}(?:[/.]|$)|cache/epub/{identifier}/|files/{identifier}/)",
                urlsplit(url).path,
            ):
                return BookLink(
                    store="gutenberg",
                    label="Project Gutenberg",
                    url=url,
                    formats=["free"],
                    match="title_author",
                    copyright_region="US",
                    language_verified=True,
                )
    return None


async def lookup_gutendex(
    client: httpx.AsyncClient, book: BookCandidate
) -> BookLink | None:
    authors = [name for name in book.authors if normalize(name)]
    if not authors:
        return None
    author_word = max(normalize(authors[0]).split(), key=len)
    response = await client.get(
        SEARCH_URL,
        params={
            "search": (book.title + " " + author_word)[:240],
            "languages": book.language,
            "copyright": "false",
        },
        timeout=4.0,
    )
    response.raise_for_status()
    return parse_gutendex(response.json(), book)
