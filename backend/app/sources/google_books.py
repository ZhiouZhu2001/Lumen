import logging
from decimal import Decimal
from typing import Any

import httpx
from pydantic import ValidationError

from app.sources.isbn import to_isbn13
from app.sources.schemas import BookCandidate, Language, Rating

logger = logging.getLogger(__name__)

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
SOURCE = "google_books"


async def search_google_books(
    client: httpx.AsyncClient,
    query: str,
    language: Language,
    api_key: str | None = None,
    max_results: int = 20,
) -> list[BookCandidate]:
    """Search Google Books. Raises httpx.HTTPError if the request fails."""
    params: dict[str, str | int] = {
        "q": query,
        "langRestrict": language,
        "printType": "books",
        "maxResults": max_results,
    }
    if api_key:
        params["key"] = api_key
    response = await client.get(GOOGLE_BOOKS_URL, params=params)
    response.raise_for_status()
    return parse_google_books(response.json(), language)


def parse_google_books(
    payload: dict[str, Any], language: Language
) -> list[BookCandidate]:
    """Turn a Google Books response into candidates, skipping unusable items."""
    books = []
    for item in payload.get("items", []):
        try:
            book = _parse_volume(item, language)
        except ValidationError as e:
            logger.warning(
                "Skipping invalid Google Books item %s: %s", item.get("id"), e
            )
            continue
        if book is not None:
            books.append(book)
    return books


def _parse_volume(item: dict[str, Any], language: Language) -> BookCandidate | None:

    info = item.get("volumeInfo", {})

    isbn13 = _pick_isbn13(info.get("industryIdentifiers", []))
    if isbn13 is None:
        return None  # spec: books without an ISBN are dropped
    if info.get("language") != language:
        return None  # langRestrict is a hint, not a guarantee

    return BookCandidate(
        isbn13=isbn13,
        title=info.get("title", ""),
        authors=info.get("authors", []),
        language=language,
        description=info.get("description"),
        cover_url=_cover_url(info.get("imageLinks", {})),
        page_count=info.get("pageCount") or None,
        published_year=_year(info.get("publishedDate")),
        genres=info.get("categories", []),
        rating=_rating(info),
        source=SOURCE,
    )


def _pick_isbn13(identifiers: list[dict[str, str]]) -> str | None:
    # Prefer a real ISBN-13; fall back to converting an ISBN-10.
    for wanted in ("ISBN_13", "ISBN_10"):
        for ident in identifiers:
            if ident.get("type") == wanted:
                isbn13 = to_isbn13(ident.get("identifier", ""))
                if isbn13:
                    return isbn13
    return None


def _cover_url(image_links: dict[str, str]) -> str | None:
    url = image_links.get("thumbnail") or image_links.get("smallThumbnail")
    return url.replace("http://", "https://", 1) if url else None


def _year(published_date: str | None) -> int | None:
    # Google returns "2009", "2009-02" or "2009-02-24"
    if published_date and published_date[:4].isdigit():
        return int(published_date[:4])
    return None


def _rating(info: dict[str, Any]) -> Rating | None:
    value, count = info.get("averageRating"), info.get("ratingsCount")
    if value is None or not count:
        return None
    return Rating(value=Decimal(str(value)), count=count, source="Google Books")
