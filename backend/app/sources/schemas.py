from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["es", "en"]


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
