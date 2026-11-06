"""Six specification checks; absent product evidence never counts as a pass."""

from collections import Counter
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.graph.state import SearchState
from app.grounding import unknown_proper_words
from app.sources.isbn import to_isbn13
from app.sources.schemas import Language

CHECK_NAMES = ("authenticity", "language", "count", "links", "reason", "latency")
STORE_HOSTS = {
    "amazon_es": "amazon.es",
    "apple_books": "books.apple.com",
    "gutenberg": "gutenberg.org",
    "casa_del_libro": "casadellibro.com",
    "abacus": "abacus.coop",
    "norma_comics": "normacomics.com",
}
Status = Literal["pass", "fail", "blocked", "not_applicable"]


class QueryFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    genre: str | None = None
    era: str | None = None
    length: Literal["short", "medium", "long"] | None = None
    free_only: bool = False


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    query: str = Field(min_length=3, max_length=300)
    language: Language
    category: Literal["normal", "niche", "nonsense"] = "normal"
    filters: QueryFilters = Field(default_factory=QueryFilters)


class QuerySuite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cases: list[EvalCase]

    @model_validator(mode="after")
    def validate_coverage(self):
        if len(self.cases) != 20:
            raise ValueError("The full suite must contain exactly 20 cases")
        if Counter(c.language for c in self.cases) != {"en": 10, "es": 10}:
            raise ValueError("The suite must contain 10 English and 10 Spanish cases")
        if len({c.id for c in self.cases}) != 20:
            raise ValueError("Case IDs must be unique")
        if len({(c.language, c.query.casefold()) for c in self.cases}) != 20:
            raise ValueError("Queries must be distinct within each language")
        for language in ("en", "es"):
            cases = [c for c in self.cases if c.language == language]
            if sum(c.category == "nonsense" for c in cases) != 1:
                raise ValueError("Each language must have exactly one nonsense case")
            if not any(c.category == "niche" for c in cases):
                raise ValueError("Each language must have a niche case")
            if not any(c.filters.free_only for c in cases):
                raise ValueError("Each language must have a free-only case")
            if not any(c.filters.era and c.filters.length for c in cases):
                raise ValueError(
                    "Each language must have an era/length constraint case"
                )
            if not any(
                any(
                    word in (c.filters.genre or "")
                    for word in ("comic", "manga", "graphic novel")
                )
                for c in cases
            ):
                raise ValueError("Each language must have a comics case")
        return self


def load_suite(path: Path) -> QuerySuite:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise ValueError("Invalid query-suite YAML") from error
    return QuerySuite.model_validate(data)


class CheckResult(BaseModel):
    status: Status
    detail: str


class EvalLink(BaseModel):
    store: Literal[
        "amazon_es",
        "apple_books",
        "gutenberg",
        "casa_del_libro",
        "abacus",
        "norma_comics",
    ]
    url: str


def outcome(ok: bool, success: str, failure: str) -> CheckResult:
    return CheckResult(
        status="pass" if ok else "fail", detail=success if ok else failure
    )


def check_links(
    case: EvalCase, state: SearchState, links: dict[str, list[EvalLink]] | None
) -> CheckResult:
    if links is None:
        return CheckResult(
            status="blocked", detail="Book-card/store-link adapter is not implemented"
        )
    candidates = {b.isbn13: b for b in state["candidates"]}
    problems = []
    for pick in state["picks"]:
        book = candidates.get(pick.isbn13)
        channels = links.get(pick.isbn13, [])
        if not channels:
            problems.append(f"{pick.isbn13}: no buying or reading link")
        for link in channels:
            try:
                url = urlsplit(link.url)
                host = url.hostname or ""
                expected_host = STORE_HOSTS[link.store]
                valid_url = (
                    url.scheme == "https"
                    and (host == expected_host or host.endswith("." + expected_host))
                    and not url.username
                    and not url.password
                    and url.port in (None, 443)
                )
            except ValueError:
                valid_url = False
            if not valid_url:
                problems.append(f"{pick.isbn13}: invalid HTTPS store link")
            if case.language == "en" and link.store in {
                "casa_del_libro",
                "abacus",
                "norma_comics",
            }:
                problems.append(
                    f"{pick.isbn13}: Spanish-only channel on an English book"
                )
            genres = " ".join(book.genres).casefold() if book else ""
            if link.store == "norma_comics" and not any(
                name in genres for name in ("comic", "manga", "graphic novel")
            ):
                problems.append(f"{pick.isbn13}: Norma Comics on a non-comic book")
        if case.filters.free_only and not any(
            link.store == "gutenberg" for link in channels
        ):
            problems.append(
                f"{pick.isbn13}: no public-domain channel supplied by the card adapter"
            )
    return outcome(
        not problems,
        "Store-language, genre and free-only rules satisfied",
        "; ".join(problems),
    )


def evaluate_case(
    case: EvalCase,
    state: SearchState,
    *,
    links: dict[str, list[EvalLink]] | None = None,
    first_book_sse_ms: float | None = None,
) -> dict[str, CheckResult]:
    candidates = {b.isbn13: b for b in state["candidates"]}
    picks = state["picks"]
    isbns = [p.isbn13 for p in picks]
    authentic = all(isbn in candidates and to_isbn13(isbn) == isbn for isbn in isbns)
    correct_language = all(
        p.isbn13 in candidates and candidates[p.isbn13].language == case.language
        for p in picks
    )
    minimum = 0 if case.category == "nonsense" else 5
    maximum = 0 if case.category == "nonsense" else 10
    if case.category == "niche" and state["retries"] == 2:
        minimum = 1  # The specification permits fewer books after retry exhaustion.
    valid_count = minimum <= len(picks) <= maximum
    reason_problems = []
    for pick in picks:
        book = candidates.get(pick.isbn13)
        if (
            not book
            or not book.description
            or not book.description.strip()
            or not pick.reason.strip()
        ):
            reason_problems.append(f"{pick.isbn13}: missing reason or description")
        elif unknown := unknown_proper_words(
            pick.reason, f"{book.title} {book.description}"
        ):
            reason_problems.append(
                f"{pick.isbn13}: unsupported proper words {', '.join(unknown)}"
            )
    if case.category == "nonsense":
        latency = CheckResult(
            status="not_applicable",
            detail="No first book is expected for nonsense input",
        )
    elif first_book_sse_ms is None:
        latency = CheckResult(
            status="blocked",
            detail="No HTTP SSE first-book measurement; graph duration is not a substitute",
        )
    else:
        latency = outcome(
            0 <= first_book_sse_ms <= 15_000,
            f"First SSE book at {first_book_sse_ms:.0f} ms",
            f"First SSE book outside the 15-second target: {first_book_sse_ms:.0f} ms",
        )
    return {
        "authenticity": outcome(
            authentic and len(isbns) == len(set(isbns)),
            "All recommended ISBNs are unique retrieved candidates",
            "Unknown, invalid or duplicated recommended ISBN",
        ),
        "language": outcome(
            correct_language,
            "Recommendation languages match the request",
            "A recommendation has missing or mismatched language evidence",
        ),
        "count": outcome(
            valid_count,
            f"{len(picks)} recommendations within {minimum}-{maximum}",
            f"Expected {minimum}-{maximum}, received {len(picks)}",
        ),
        "links": check_links(case, state, links),
        "reason": outcome(
            not reason_problems,
            "Reasons have descriptions and pass the proper-word heuristic",
            "; ".join(reason_problems),
        ),
        "latency": latency,
    }


def gate_passed(results: list[dict], expected_ids: set[str]) -> bool:
    if (
        len(expected_ids) != 20
        or len(results) != 20
        or {r["id"] for r in results} != expected_ids
    ):
        return False
    return all(
        not result.get("error_code")
        and not result.get("unsupported_filters")
        and set(result["checks"]) == set(CHECK_NAMES)
        and all(
            check["status"] == "pass"
            or (
                name == "latency"
                and result.get("category") == "nonsense"
                and check["status"] == "not_applicable"
            )
            for name, check in result["checks"].items()
        )
        for result in results
    )
