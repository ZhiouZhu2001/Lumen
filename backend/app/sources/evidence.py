"""Keep original catalog objects separate from public book serialization."""

from copy import deepcopy
from datetime import datetime

from app.sources.schemas import BookCandidate, CatalogRecord


def record(payload: dict, fetched_at: datetime | None = None) -> CatalogRecord:
    # Callers may reuse or enrich their decoded response after parsing it.
    return CatalogRecord(payload=deepcopy(payload), fetched_at=fetched_at)


def mark_fetched(book: BookCandidate, fetched_at: datetime | None) -> BookCandidate:
    return book.model_copy(
        update={
            "catalog_fetched_at": fetched_at,
            "provider_records": {
                kind: [
                    value.model_copy(update={"fetched_at": fetched_at})
                    for value in values
                ]
                for kind, values in book.provider_records.items()
            },
        }
    )
