from app.sources.schemas import BookCandidate

# Fields the secondary source may fill when the primary one is missing them.
# The title is deliberately not here: the primary title always wins.
FILLABLE_FIELDS = (
    "authors",
    "description",
    "cover_url",
    "page_count",
    "published_year",
    "genres",
    "rating",
)


def merge_candidates(
    primary: list[BookCandidate],
    secondary: list[BookCandidate],
) -> list[BookCandidate]:
    """Combine two sources into one list with one book per ISBN-13.

    The primary source wins; the secondary source only fills its gaps.
    """
    # A dict keeps insertion order, so primary books come first.
    merged: dict[str, BookCandidate] = {}
    for book in primary:
        merged.setdefault(book.isbn13, book)  # duplicates: keep the first.
    seen_secondary: set[tuple[str, str]] = set()
    for book in secondary:
        key = (book.isbn13, book.source)
        if key in seen_secondary:
            continue
        seen_secondary.add(key)
        existing = merged.get(book.isbn13)
        if existing is None:
            merged[book.isbn13] = book
        else:
            # Later rounds may fill gaps even when the source was already seen.
            merged[book.isbn13] = _fill_gaps(existing, book)
    return list(merged.values())


def _fill_gaps(base: BookCandidate, extra: BookCandidate) -> BookCandidate:
    updates = {
        field: getattr(extra, field)
        for field in FILLABLE_FIELDS
        if not _has_value(getattr(base, field)) and _has_value(getattr(extra, field))
    }
    sources = [*base.source.split("+"), *extra.source.split("+")]
    updates["source"] = "+".join(dict.fromkeys(sources))
    # model_copy returns a NEW object; the input books are never modified
    return base.model_copy(update=updates)


def _has_value(value: object) -> bool:
    return bool(value.strip()) if isinstance(value, str) else bool(value)
