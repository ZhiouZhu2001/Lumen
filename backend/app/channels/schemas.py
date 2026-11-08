from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.sources.schemas import BookCandidate

BookFormat = Literal["paper", "kindle", "ebook", "apple_books", "free"]
LookupStatus = Literal["matched", "not_found", "unavailable", "insufficient_metadata"]


class BookLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    store: str
    label: str
    url: str
    formats: list[BookFormat]
    match: Literal["isbn_search", "title_author"]
    language_verified: bool = False
    copyright_region: Literal["US"] | None = None

    @field_validator("url")
    @classmethod
    def require_https(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ValueError("Channel links must use HTTPS without credentials")
        return value


class BookCard(BookCandidate):
    rank: int = Field(ge=1, le=10)
    reason: str = Field(min_length=1)
    links: list[BookLink]
    formats: list[BookFormat]


class CardBatch(BaseModel):
    cards: list[BookCard]
    lookups: dict[str, dict[str, LookupStatus]]
