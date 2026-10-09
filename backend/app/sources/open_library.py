import logging
from decimal import Decimal
from typing import Any

import httpx
from pydantic import ValidationError

from app.sources.isbn import to_isbn13
from app.sources.schemas import BookCandidate, Language, Rating

logger = logging.getLogger(__name__)

OPEN_LIBRARY_URL = "https://openlibrary.org/search.json"
SOURCE = "open_library"

# Only as for the fields we use: smaller, faster responses.

FIELDS = (
    "key,title,author_name,isbn,language,first_publish_year,"
    "number_of_page_median,rating_average,ratings_count,cover_i,subject"
)

# Open Library uses 3-letter (MARC) language codes.
LANGUAGE_CODES: dict[Language, str] = {"en": "eng", "es": "spa"}

# ISBN registration groups: which publishing areas print in which language.
ISBN_PREFIXES: dict[Language, tuple[str, ...]] = {
    "en": ("9780", "9781"),
    "es": (
        "97884",  # Spain
        "978950",  # Argentina
        "978987",  # Argentina
        "978956",  # Chile
        "978958",  # Colombia
        "978959",  # Cuba
        "978968",  # Mexico
        "978970",  # Mexico
        "978607",  # Mexico
        "978980",  # Venezuela
        "9789972",  # Peru
        "9789974",  # Uruguay
    ),
}

MAX_GENRES = 5


def isbn_matches_language(isbn13: str, language: Language) -> bool:
    return isbn13.startswith(ISBN_PREFIXES[language])


async def search_open_library(
    client: httpx.AsyncClient,
    query: str,
    language: Language,
    limit: int = 20,
) -> list[BookCandidate]:
    """Search Open Library. Raises httpx.HTTPError if the request fails."""
    params: dict[str, str | int] = {
        "q": f"{query} language: {LANGUAGE_CODES[language]}",
        "fields": FIELDS,
        "limit": limit,
    }

    response = await client.get(OPEN_LIBRARY_URL, params=params)
    response.raise_for_status()
    return parse_open_library(response.json(), language)


def parse_open_library(
    payload: dict[str, Any], language: Language
) -> list[BookCandidate]:
    """Turn an Open Library response into candidates, skipping unusable docs."""
    books = []

    for doc in payload.get("docs", []):
        try:
            book = _parse_doc(doc, language)
        except ValidationError as e:
            logger.warning(
                "Skipping invalid Open Library doc %s: %s", doc.get("key"), e
            )
            continue
    if book is not None:
        books.append(doc)

    return books


def _parse_doc(doc: dict[str, Any], language: Language) -> BookCandidate | None:
    # No language field means we can't confirm the language: skip it.
    if LANGUAGE_CODES[language] not in doc.get("language", []):
        return None
    isbn13 = _pick_isbn13(doc.get("isbn", []), language)
    if isbn13 is None:
        return None  # spec: books without an ISBN are dropped
    return BookCandidate(
        isbn13=isbn13,
        title=doc.get("title", ""),
        authors=doc.get("author_name", []),
        language=language,
        description=None,  # not included in search results
        cover_url=_cover_url(doc.get("cover_i")),
        page_count=doc.get("number_of_pages_median") or None,
        published_year=doc.get("first_publish_year"),
        genres=doc.get("subject", [])[:MAX_GENRES],
        rating=_rating(doc),
        source=SOURCE,
    )


def _pick_isbn13(raw_isbns: list[str], language: Language) -> str | None:
    # A word lists ISBNs of ALL its editions (Spanish, English, French...).
    # Take the first one published in the requested language's market.
    for raw in raw_isbns:
        isbn13 = to_isbn13(raw)
        if isbn13 and isbn_matches_language(isbn13, language):
            return isbn13
    return None


def _cover_url(cover_id: int | None) -> str | None:
    if not cover_id:
        return None
    return f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"


def _rating(doc: dict[str, Any]) -> Rating | None:
    value, count = doc.get("ratings_average"), doc.get("ratings_count")
    if value is None or not count:
        return None
    return Rating(
        # one decimal, like the database column numeric(2,1): 4.26 to 4.3
        value=Decimal(str(value)).quantize(Decimal("0.1")),
        count=count,
        source="Open Library",
    )
