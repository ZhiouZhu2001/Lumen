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
    primary: list[BookCandidate], secondary : list[BookCandidate],
) -> list[BookCandidate]:
    """Combine two sources into one list with one book per ISBN-13.

    The primary source wins; the secondary source only fills its gaps.
    """
    # A dict keeps insertion order, so primary books come first.
    merged: dict[str, BookCandidate] = {}
    for book in primary:
        merged.setdefault(book.isbn13, book)  # duplicates: keep the first.
    for book in secondary:
        existing = merged.get(book.isbn13)
        if existing is None:
            merged[book.isbn13] = book
        # don't merge the same source in twice (duplicate inside secondary)
        elif book.source not in existing.source.split("+"):
            merged[book.isbn13] = _fill_gaps(existing, book)
    return list(merged.values())


def _fill_gaps(base: BookCandidate, extra: BookCandidate) -> BookCandidate:
    updates = {
        field: getattr(extra, field)
        for field in FILLABLE_FIELDS
        if not getattr(base, field) and getattr(extra, field)
    }
    updates["source"] = f"{base.source} + {extra.source}"
    # model_copy returns a NEW object; the input books are never modified
    return base.model_copy(update=updates)
