"""Exact-ISBN metadata reads for saved details, separate from search retrieval."""

import asyncio
import re
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from app.sources.google_books import GOOGLE_BOOKS_URL, parse_google_books
from app.sources.isbn import to_isbn13
from app.sources.open_library import LANGUAGE_CODES
from app.sources.schemas import BookCandidate, Language


async def _google(client, isbn13, language, api_key):
    started = datetime.now(UTC)
    response = await client.get(
        GOOGLE_BOOKS_URL,
        params={
            "q": f"isbn:{isbn13}",
            "langRestrict": language,
            "printType": "books",
            "maxResults": 5,
        },
        headers={"X-Goog-Api-Key": api_key} if api_key else {},
        timeout=2,
    )
    response.raise_for_status()
    books = parse_google_books(response.json(), language)
    return next(
        (
            book.model_copy(
                update={
                    "catalog_fetched_at": response.extensions.get(
                        "catalog_fetched_at", started
                    )
                }
            )
            for book in books
            if book.isbn13 == isbn13
        ),
        None,
    )


def parse_open_library_edition(payload, isbn13: str, language: Language):
    """Do not substitute work-level language/ISBNs for an identified edition."""
    if not isinstance(payload, dict):
        return None
    identifiers = [
        value
        for field in ("isbn_13", "isbn_10")
        for value in payload.get(field, [])
        if isinstance(value, str)
    ]
    languages = payload.get("languages", [])
    if isbn13 not in {to_isbn13(value) for value in identifiers} or not any(
        isinstance(value, dict)
        and value.get("key") == f"/languages/{LANGUAGE_CODES[language]}"
        for value in languages
    ):
        return None
    description = payload.get("description")
    if isinstance(description, dict):
        description = description.get("value")
    if not isinstance(description, str):
        description = None
    covers = payload.get("covers", [])
    cover = next((v for v in covers if type(v) is int and v > 0), None)
    year = re.search(
        r"(?<!\d)(?:1\d{3}|20\d{2})(?!\d)", str(payload.get("publish_date", ""))
    )
    # Editions normally contain author IDs, not names. Keep existing names rather
    # than inventing them or issuing an unbounded series of author lookups.
    authors = payload.get("authors", [])
    names = [
        a["name"]
        for a in authors
        if isinstance(a, dict) and isinstance(a.get("name"), str)
    ]
    if len(names) != len(authors):
        names = []
    try:
        return BookCandidate(
            isbn13=isbn13,
            title=payload.get("title", ""),
            authors=names,
            language=language,
            description=description,
            cover_url=f"https://covers.openlibrary.org/b/id/{cover}-M.jpg"
            if cover
            else None,
            page_count=payload.get("number_of_pages") or None,
            published_year=int(year[0]) if year else None,
            genres=[v for v in payload.get("subjects", []) if isinstance(v, str)][:5],
            source="open_library",
        )
    except ValidationError:
        return None


async def _open_library(client, isbn13, language):
    started = datetime.now(UTC)
    response = await client.get(
        f"https://openlibrary.org/isbn/{isbn13}.json", timeout=2
    )
    if response.status_code in (301, 302, 307, 308):
        target = response.request.url.join(response.headers.get("location", ""))
        if (
            target.scheme != "https"
            or target.host != "openlibrary.org"
            or target.port not in (None, 443)
            or target.username
            or target.password
            or target.query
            or not re.fullmatch(r"/books/OL\d+M.json", target.path)
        ):
            return None
        response = await client.get(target, timeout=2)
    response.raise_for_status()
    book = parse_open_library_edition(response.json(), isbn13, language)
    return book.model_copy(update={"catalog_fetched_at": started}) if book else None


async def lookup_edition(
    client: httpx.AsyncClient,
    isbn13: str,
    language: Language,
    api_key: str | None = None,
) -> BookCandidate | None:
    if to_isbn13(isbn13) != isbn13:
        raise ValueError("A canonical ISBN-13 is required")
    # Start both existing providers, prefer the primary and cancel unnecessary
    # fallback work. The caller bounds the entire operation to three seconds.
    primary = asyncio.create_task(_google(client, isbn13, language, api_key))
    secondary = asyncio.create_task(_open_library(client, isbn13, language))
    try:
        for task in (primary, secondary):
            try:
                book = await task
                if book is not None:
                    return book
            except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
                continue
        return None
    finally:
        for task in (primary, secondary):
            if not task.done():
                task.cancel()
        await asyncio.gather(primary, secondary, return_exceptions=True)
