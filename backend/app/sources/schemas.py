from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, JsonValue

Language = Literal["es", "en"]
RecordKind = Literal[
    "google_books", "open_library_search", "open_library_work", "open_library_edition"
]


class CatalogRecord(BaseModel):
    """One original book/work object, without request headers or reader input."""

    payload: dict[str, JsonValue]
    fetched_at: AwareDatetime | None = None


class Rating(BaseModel):
    value: Decimal = Field(ge=0, le=5)
    count: int = Field(ge=0)
    source: str


class BookCandidate(BaseModel):
    """One book as returned by a bibliographic source, already normalized."""

    isbn13: str = Field(pattern=r"^[0-9]{13}$")
    title: str = Field(min_length=1)
    authors: list[str] = []
    language: Language
    description: str | None = None
    cover_url: str | None = None
    page_count: int | None = Field(default=None, gt=0)
    published_year: int | None = None
    genres: list[str] = []
    rating: Rating | None = None
    source: str
    work_key: str | None = Field(default=None, pattern=r"^/works/OL\d+W$", exclude=True)
    catalog_fetched_at: AwareDatetime | None = Field(default=None, exclude=True)
    provider_records: dict[RecordKind, list[CatalogRecord]] = Field(
        default_factory=dict, exclude=True, repr=False
    )
