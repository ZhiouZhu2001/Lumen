from decimal import Decimal
from typing import Any

from app.sources.merge import merge_candidates
from app.sources.schemas import BookCandidate, Rating


def google(isbn13: str, **fields: Any) -> BookCandidate:
    return BookCandidate(
        isbn13=isbn13,
        title=fields.pop("title", f"Google {isbn13}"),
        language="es",
        source="google_books",
        **fields,
    )


def open_library(isbn13: str, **fields: Any) -> BookCandidate:
    return BookCandidate(
        isbn13=isbn13,
        title=fields.pop("title", f"Open Library {isbn13}"),
        language="es",
        source="open_library",
        **fields,
    )


A, B, C, D = "9780307474728", "9788437604947", "9788401242267", "9789500712347"


def test_empty_inputs_give_empty_result() -> None:
    assert merge_candidates([], []) == []


def test_without_overlap_google_comes_first_then_open_library() -> None:
    result = merge_candidates(
        [google(A), google(B)], [open_library(C), open_library(D)]
    )
    assert [b.isbn13 for b in result] == [A, B, C, D]


def test_same_isbn_becomes_one_book_with_google_title() -> None:
    result = merge_candidates(
        [google(A, title="Cien años de soledad")], [open_library(A)]
    )
    assert len(result) == 1
    assert result[0].title == "Cien años de soledad"
    assert result[0].source == "google_books+open_library"


def test_open_library_fills_only_the_gaps() -> None:
    result = merge_candidates(
        [google(A, page_count=496, description="From Google")],
        [
            open_library(
                A,
                page_count=471,
                published_year=1967,
                cover_url="https://covers.openlibrary.org/b/id/1-M.jpg",
                authors=["Gabriel García Márquez"],
                genres=["Fiction"],
            )
        ],
    )
    book = result[0]
    assert book.page_count == 496  # Google had it: kept
    assert book.description == "From Google"  # Google had it: kept
    assert book.published_year == 1967  # Google was missing it: filled
    assert book.cover_url == "https://covers.openlibrary.org/b/id/1-M.jpg"
    assert book.authors == ["Gabriel García Márquez"]  # empty list counts as a gap
    assert book.genres == ["Fiction"]


def test_rating_keeps_its_original_source() -> None:
    ol_rating = Rating(value=Decimal("4.3"), count=310, source="Open Library")
    google_rating = Rating(value=Decimal("4.5"), count=120, source="Google Books")

    filled = merge_candidates([google(A)], [open_library(A, rating=ol_rating)])
    kept = merge_candidates(
        [google(B, rating=google_rating)], [open_library(B, rating=ol_rating)]
    )

    assert filled[0].rating == ol_rating  # spec: always show where a rating came from
    assert kept[0].rating == google_rating


def test_duplicates_inside_one_source_keep_the_first() -> None:
    result = merge_candidates(
        [google(A, title="First"), google(A, title="Second")],
        [
            open_library(A),
            open_library(A),
            open_library(B, title="First OL"),
            open_library(B, title="Second OL"),
        ],
    )
    assert [(b.isbn13, b.title, b.source) for b in result] == [
        (A, "First", "google_books+open_library"),
        (B, "First OL", "open_library"),
    ]


def test_inputs_are_not_modified() -> None:
    original = google(A)
    merge_candidates([original], [open_library(A, published_year=1967)])
    assert original.published_year is None
    assert original.source == "google_books"