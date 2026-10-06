import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKey,
    MetaData,
    Numeric,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names, so migrations can find them later
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint("isbn13 ~ '^[0-9]{13}$'", name="isbn13_digits"),
        CheckConstraint("language IN ('en', 'es')", name="ck_books_language_supported"),
        CheckConstraint(
            "(rating_value IS NULL AND rating_count IS NULL AND rating_source IS NULL)"
            " OR (rating_value IS NOT NULL AND rating_count IS NOT NULL"
            " AND rating_source IS NOT NULL)",
            name="rating_all_or_nothing",
        ),
        CheckConstraint(
            "(rating_value IS NULL OR (rating_value >= 0 AND rating_value <= 5))",
            name="rating_value_range",
        ),
    )

    isbn13: Mapped[str] = mapped_column(CHAR(13), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list[str]] = mapped_column(ARRAY(Text))
    language: Mapped[str] = mapped_column(CHAR(2))
    description: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None]
    published_year: Mapped[int | None]
    genres: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    rating_value: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    rating_count: Mapped[int | None]
    rating_source: Mapped[str | None] = mapped_column(Text)
    formats: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

class Search(Base):
    __tablename__ = "searches"
    __table_args__ = (
        CheckConstraint("language IN ('es','en')", name="ck_searches_language_supported"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query_text: Mapped[str] = mapped_column(Text)
    parsed_query: Mapped[str | None] = mapped_column(JSONB)
    language: Mapped[str] = mapped_column(CHAR(2))
    filters: Mapped[str] = mapped_column(JSONB, server_default="{}")
    candidate_count: Mapped[int] = mapped_column(server_default="0")
    retries: Mapped[int] = mapped_column(server_default="0")
    duration_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), index=True
    )
    
class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (
        CheckConstraint("rank BETWEEN 1 AND 10", name="rank_range"),
    )

    search_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("searches.id", ondelete="CASCADE") ,primary_key=True)
    isbn13: Mapped[str] = mapped_column(CHAR(13), ForeignKey("books.isbn13") ,primary_key=True)
    rank: Mapped[int] = mapped_column(SmallInteger)
    reason: Mapped[str] = mapped_column(Text)




