"""Validated request constraints; missing catalog metadata never proves a match."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.sources.schemas import BookCandidate


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    genre: str | None = Field(default=None, min_length=1, max_length=80)
    era: str | None = Field(default=None, pattern=r"^(18|19|20)\d0s$")
    length: Literal["short", "medium", "long"] | None = None
    # Retain false for older clients; true is rejected instead of silently ignored.
    free_only: Literal[False] = False


def constrained_query(query: str, filters: SearchFilters) -> str:
    constraints = []
    if filters.genre:
        constraints.append(f"Genre: {filters.genre}")
    if filters.era:
        start = int(filters.era[:4])
        constraints.append(f"Publication year: {start}-{start + 9}")
    if filters.length:
        constraints.append(
            "Length: "
            + {
                "short": "at most 200 pages",
                "medium": "201-400 pages",
                "long": "more than 400 pages",
            }[filters.length]
        )
    return query + (
        "\nReader's explicit filters:\n" + "\n".join(constraints) if constraints else ""
    )


def matches_metadata(book: BookCandidate, filters: SearchFilters) -> bool:
    """Genre is semantic model selection; year and length are strict code checks."""
    if filters.era:
        start = int(filters.era[:4])
        if book.published_year is None or not start <= book.published_year <= start + 9:
            return False
    if filters.length:
        if book.page_count is None:
            return False
        if filters.length == "short" and book.page_count > 200:
            return False
        if filters.length == "medium" and not 201 <= book.page_count <= 400:
            return False
        if filters.length == "long" and book.page_count <= 400:
            return False
    return True
