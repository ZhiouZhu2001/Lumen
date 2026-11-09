"""Atomic search persistence and safe public reads over the existing schema."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import case, func, insert, literal, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.authors import clean_requested_authors
from app.channels.matching import safe_url
from app.channels.rules import StoreRule, applies, load_rules, search_links
from app.channels.schemas import BookCard, BookDetails, BookLink
from app.filters import SearchFilters, matches_metadata
from app.graph.rank import ModelPick, ModelPicks, validate_picks
from app.graph.state import SearchState
from app.models import Book, Search, SearchResult
from app.sources.isbn import to_isbn13
from app.sources.schemas import BookCandidate, Rating


class StorageUnavailable(Exception):
    """Storage did not complete; callers must not report a successful save."""


def _records(book: BookCandidate) -> dict:
    return {
        kind: [record.model_dump(mode="json") for record in records]
        for kind, records in book.provider_records.items()
        if records
    }


def _merge_raw(incoming):
    # Additive extension of snapshot v1. Old rows/captures have no originals;
    # never fabricate them or erase records from an absent provider.
    existing = case(
        (
            func.jsonb_typeof(Book.raw["provider_records"]) == "object",
            Book.raw["provider_records"],
        ),
        else_=literal({}, type_=JSONB),
    )
    return incoming.op("||")(
        func.jsonb_build_object(
            "provider_records", existing.op("||")(incoming.op("->")("provider_records"))
        )
    )


class SearchRepository:
    """The caller owns the engine. Each save is one short transaction.

    All validated candidates of completed searches are cached. Search-specific
    reasons and reader text belong to searches/results, never the public snapshot.
    """

    def __init__(self, engine: AsyncEngine, *, rules: list[StoreRule] | None = None):
        self.engine = engine
        self.rules = load_rules() if rules is None else rules

    def validate_completed(
        self, state: SearchState, cards: list[BookCard], duration_ms: int
    ):
        candidates = {b.isbn13: b for b in state["candidates"]}
        for book in state["candidates"]:
            BookCandidate.model_validate(book.model_dump())
            if (
                to_isbn13(book.isbn13) != book.isbn13
                or book.language != state["language"]
                or not book.title.strip()
            ):
                raise ValueError(
                    "Persistence requires canonical language-matched candidates"
                )
        proposed = ModelPicks(
            picks=[ModelPick(isbn13=c.isbn13, reason=c.reason) for c in cards]
        )
        valid, _ = validate_picks(
            proposed,
            state["candidates"],
            state["language"],
            query=state["query"],
            requested_authors=clean_requested_authors(
                state["query"],
                state.get(
                    "request_authors",
                    state["parsed"].requested_authors if state["parsed"] else [],
                ),
            ),
        )
        if (
            not 3 <= len(state["query"]) <= 300
            or state["parsed"] is None
            or not 0 <= state["retries"] <= 2
            or duration_ms < 0
            or len(candidates) != len(state["candidates"])
            or len(cards) != len(valid)
            or [c.isbn13 for c in cards] != [p.isbn13 for p in valid]
            or [c.isbn13 for c in cards] != [p.isbn13 for p in state["picks"]]
            or [c.reason for c in cards] != [p.reason for p in state["picks"]]
            or [c.rank for c in cards] != list(range(1, len(cards) + 1))
            or [p.rank for p in state["picks"]] != list(range(1, len(cards) + 1))
        ):
            raise ValueError("Persistence requires a complete validated search")
        meaningful = state.get("request_understood", state["parsed"].is_book_request)
        if (meaningful and len(cards) < 5 and state["retries"] != 2) or (
            not meaningful and cards
        ):
            raise ValueError("Persistence requires the bounded workflow to finish")
        filters = state.get("filters", SearchFilters())
        for card in cards:
            original = candidates[card.isbn13]
            public = BookCandidate.model_validate(card.model_dump()).model_dump()
            if (
                public != original.model_dump()
                or not card.title.strip()
                or not matches_metadata(card, filters)
            ):
                raise ValueError(
                    "Stored cards must preserve retrieved metadata and filters"
                )

    async def save_completed(
        self,
        search_id: UUID,
        state: SearchState,
        cards: list[BookCard],
        duration_ms: int,
        *,
        refresh_books: bool = True,
    ) -> None:
        self.validate_completed(state, cards, duration_ms)
        values = []
        displayed = {card.isbn13: card for card in cards}
        for book in sorted(state["candidates"], key=lambda b: b.isbn13):
            card = displayed.get(book.isbn13)
            links = card.links if card else search_links(book, self.rules)
            rating = book.rating
            values.append(
                {
                    "isbn13": book.isbn13,
                    "title": book.title,
                    "authors": book.authors,
                    "language": book.language,
                    "description": book.description,
                    "cover_url": book.cover_url,
                    "page_count": book.page_count,
                    "published_year": book.published_year,
                    "genres": book.genres,
                    "rating_value": rating.value if rating else None,
                    "rating_count": rating.count if rating else None,
                    "rating_source": rating.source if rating else None,
                    "formats": list(
                        dict.fromkeys(f for link in links for f in link.formats)
                    ),
                    "fetched_at": book.catalog_fetched_at or func.now(),
                    "raw": {
                        "snapshot_version": 1,
                        "source": book.source,
                        "links": [link.model_dump(mode="json") for link in links],
                        "provider_records": _records(book),
                    },
                }
            )
        try:
            async with self.engine.begin() as connection:
                if values and not refresh_books:
                    # Cache hits create a new search/result history without
                    # overwriting newer books or pretending to fetch them again.
                    saved = set(
                        (
                            await connection.execute(
                                select(Book.isbn13).where(
                                    Book.isbn13.in_([card.isbn13 for card in cards]),
                                    Book.language == state["language"],
                                )
                            )
                        ).scalars()
                    )
                    if saved != {card.isbn13 for card in cards}:
                        raise StorageUnavailable("Cached books are no longer available")
                if values and refresh_books:
                    statement = pg_insert(Book).values(values)
                    incoming = statement.excluded
                    raw = _merge_raw(incoming.raw)
                    # Undisplayed candidates do not run channel lookups. Retain
                    # a prior optional match only while title/authors are unchanged.
                    keep_links = (
                        incoming.isbn13.not_in(list(displayed))
                        & (incoming.title == Book.title)
                        & (incoming.authors == Book.authors)
                        & (Book.raw["snapshot_version"] == literal(1, type_=JSONB))
                        & (func.jsonb_typeof(Book.raw["links"]) == "array")
                    )
                    raw = case(
                        (
                            keep_links,
                            raw.op("||")(
                                func.jsonb_build_object("links", Book.raw["links"])
                            ),
                        ),
                        else_=raw,
                    )
                    updates = {
                        "title": incoming.title,
                        "authors": case(
                            (func.cardinality(incoming.authors) > 0, incoming.authors),
                            else_=Book.authors,
                        ),
                        "genres": case(
                            (func.cardinality(incoming.genres) > 0, incoming.genres),
                            else_=Book.genres,
                        ),
                        "formats": case(
                            (keep_links, Book.formats), else_=incoming.formats
                        ),
                        "raw": raw,
                        "fetched_at": incoming.fetched_at,
                    }
                    for field in (
                        "description",
                        "cover_url",
                        "page_count",
                        "published_year",
                    ):
                        updates[field] = func.coalesce(
                            getattr(incoming, field), getattr(Book, field)
                        )
                    for field in ("rating_value", "rating_count", "rating_source"):
                        updates[field] = case(
                            (
                                incoming.rating_value.is_not(None),
                                getattr(incoming, field),
                            ),
                            else_=getattr(Book, field),
                        )
                    # Source-cache responses retain their original fetch time and
                    # must never overwrite a newer snapshot from another search.
                    updates = {
                        field: case(
                            (incoming.fetched_at >= Book.fetched_at, value),
                            else_=getattr(Book, field),
                        )
                        for field, value in updates.items()
                    }
                    statement = statement.on_conflict_do_update(
                        index_elements=[Book.isbn13],
                        set_=updates,
                        where=Book.language == incoming.language,
                    ).returning(Book.isbn13)
                    saved = set((await connection.execute(statement)).scalars())
                    if saved != {book.isbn13 for book in state["candidates"]}:
                        raise StorageUnavailable(
                            "Conflicting catalog language for an existing ISBN"
                        )
                await connection.execute(
                    insert(Search).values(
                        id=search_id,
                        query_text=state["query"],
                        language=state["language"],
                        parsed_query={
                            **state["parsed"].model_dump(mode="json"),
                            "requested_authors": state.get(
                                "request_authors", state["parsed"].requested_authors
                            ),
                        },
                        filters=state.get("filters", SearchFilters()).model_dump(
                            mode="json"
                        ),
                        candidate_count=len(state["candidates"]),
                        retries=state["retries"],
                        duration_ms=duration_ms,
                    )
                )
                if cards:
                    await connection.execute(
                        insert(SearchResult),
                        [
                            {
                                "search_id": search_id,
                                "isbn13": card.isbn13,
                                "rank": card.rank,
                                "reason": card.reason,
                            }
                            for card in cards
                        ],
                    )
        except SQLAlchemyError as error:
            raise StorageUnavailable(
                "Search storage is temporarily unavailable"
            ) from error

    def _details(self, row) -> BookDetails:
        raw = row["raw"] if isinstance(row["raw"], dict) else {}
        source = raw.get("source")
        # Unknown legacy raw fields are not a public provenance contract.
        if (
            not isinstance(source, str)
            or not source
            or any(
                part not in {"google_books", "open_library"}
                for part in source.split("+")
            )
        ):
            source = "catalog_cache"
        rating = None
        if all(
            row[f"rating_{field}"] is not None for field in ("value", "count", "source")
        ):
            rating = Rating(
                value=row["rating_value"],
                count=row["rating_count"],
                source=row["rating_source"],
            )
        book = BookCandidate(
            **{
                key: row[key]
                for key in (
                    "isbn13",
                    "title",
                    "authors",
                    "language",
                    "description",
                    "cover_url",
                    "page_count",
                    "published_year",
                    "genres",
                )
            },
            rating=rating,
            source=source,
        )
        links = search_links(book, self.rules)
        stored = raw.get("links", []) if raw.get("snapshot_version") == 1 else []
        if isinstance(stored, list):
            for rule in self.rules:
                if (
                    rule.mode != "lookup"
                    or rule.provider != "apple_books"
                    or not applies(rule, book)
                ):
                    continue
                for value in stored:
                    try:
                        link = BookLink.model_validate(value)
                    except (ValueError, TypeError):
                        continue
                    if (
                        link.store == rule.id
                        and link.match == "title_author"
                        and safe_url(link.url, rule.host)
                    ):
                        links.append(
                            link.model_copy(
                                update={
                                    "label": rule.label,
                                    "formats": list(rule.formats),
                                    "language_verified": False,
                                    "copyright_region": None,
                                }
                            )
                        )
                        break
        return BookDetails(
            **book.model_dump(),
            links=links,
            formats=list(dict.fromkeys(f for link in links for f in link.formats)),
            fetched_at=row["fetched_at"],
        )

    async def get_book(self, isbn13: str) -> BookDetails | None:
        if to_isbn13(isbn13) != isbn13:
            raise ValueError("A valid ISBN-13 is required")
        try:
            async with self.engine.connect() as connection:
                row = (
                    (
                        await connection.execute(
                            select(Book.__table__).where(Book.isbn13 == isbn13)
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            return self._details(row) if row else None
        except (SQLAlchemyError, ValidationError, ValueError) as error:
            raise StorageUnavailable(
                "Book storage is temporarily unavailable"
            ) from error

    async def refresh_book(
        self, original: BookDetails, candidate: BookCandidate
    ) -> BookDetails | None:
        # Revalidate mutable model instances before performing the targeted update.
        book = BookCandidate.model_validate(candidate.model_dump())
        fetched = candidate.catalog_fetched_at
        if (
            book.isbn13 != original.isbn13
            or book.language != original.language
            or to_isbn13(book.isbn13) != book.isbn13
            or not book.title.strip()
            or book.source not in {"google_books", "open_library"}
            or fetched is None
            or fetched.tzinfo is None
            or not original.fetched_at < fetched <= datetime.now(UTC)
        ):
            raise ValueError("Refresh requires newer exact-ISBN language-matched data")
        merged = book.model_copy(
            update={
                field: getattr(book, field) or getattr(original, field)
                for field in (
                    "authors",
                    "description",
                    "cover_url",
                    "page_count",
                    "published_year",
                    "genres",
                    "rating",
                )
            }
        )
        links = search_links(merged, self.rules)
        # Optional title/author matches remain valid only for unchanged identity.
        if merged.title == original.title and merged.authors == original.authors:
            links.extend(
                link for link in original.links if link.match == "title_author"
            )
        values = merged.model_dump(exclude={"rating", "source", "isbn13", "language"})
        values.update(
            rating_value=merged.rating.value if merged.rating else None,
            rating_count=merged.rating.count if merged.rating else None,
            rating_source=merged.rating.source if merged.rating else None,
            formats=list(dict.fromkeys(f for link in links for f in link.formats)),
            raw=_merge_raw(
                literal(
                    {
                        "snapshot_version": 1,
                        "source": merged.source,
                        "links": [link.model_dump(mode="json") for link in links],
                        "provider_records": _records(candidate),
                    },
                    type_=JSONB,
                )
            ),
            fetched_at=fetched,
        )
        try:
            async with self.engine.begin() as connection:
                row = (
                    (
                        await connection.execute(
                            update(Book)
                            .where(
                                Book.isbn13 == original.isbn13,
                                Book.language == original.language,
                                Book.fetched_at == original.fetched_at,
                            )
                            .values(**values)
                            .returning(*Book.__table__.c)
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
            # A concurrent search/refresh won. Read it instead of overwriting it.
            return self._details(row) if row else await self.get_book(original.isbn13)
        except (SQLAlchemyError, ValidationError) as error:
            raise StorageUnavailable(
                "Book refresh is temporarily unavailable"
            ) from error
