from app.graph.rank import (
    MAX_CANDIDATES,
    MAX_DESCRIPTION_CHARS,
    MAX_PICKS,
    ModelPick,
    ModelPicks,
    clean_picks,
    format_candidates,
    select_for_ranking,
)
from app.sources.schemas import BookCandidate


def book(n: int, description: str | None = "A novel.") -> BookCandidate:
    return BookCandidate(
        isbn13=f"978{n:010d}",
        title=f"Book {n}",
        authors=["Ana García"],
        language="es",
        description=description,
        source="google_books",
    )


def picks(*items: tuple[str, str]) -> ModelPicks:
    return ModelPicks(picks=[ModelPick(isbn13=i, reason=r) for i, r in items])


CANDIDATES = [book(1), book(2), book(3)]
ISBN_1, ISBN_2, ISBN_3 = (b.isbn13 for b in CANDIDATES)


def test_books_without_a_description_are_left_out() -> None:
    books = [book(1, None), book(2), book(3, ""), book(4)]
    assert [b.title for b in select_for_ranking(books)] == ["Book 2", "Book 4"]
    assert select_for_ranking([book(1, None)]) == []


def test_at_most_30_books_are_sent_to_the_model() -> None:
    assert len(select_for_ranking([book(n) for n in range(50)])) == MAX_CANDIDATES

def test_format_shows_the_fields_and_cuts_long_descriptions() -> None:
    text = format_candidates([book(1, "x" * 5000)])
    assert f"ISBN: {ISBN_1}\nTitle: Book 1\nAuthors: Ana García\n" in text
    assert "x" * MAX_DESCRIPTION_CHARS in text
    assert "x" * (MAX_DESCRIPTION_CHARS + 1) not in text

def test_good_picks_are_kept_and_ranked_in_order() -> None:
    result = clean_picks(picks((ISBN_2, "Fits."), (ISBN_1, "Also fits.")), CANDIDATES)
    assert [(p.isbn13, p.rank, p.reason) for p in result] == [
        (ISBN_2, 1, "Fits."),
        (ISBN_1, 2, "Also fits."),
    ]


def test_invented_isbns_are_dropped() -> None:
    result = clean_picks(
        picks(("9780000000000", "Made up."), (ISBN_1, "Real.")), CANDIDATES
    )
    assert [(p.isbn13, p.rank) for p in result] == [(ISBN_1, 1)]


def test_isbn_with_hyphens_or_spaces_is_still_recognized() -> None:
    messy = f" {ISBN_1[:3]}-{ISBN_1[3:]} "
    result = clean_picks(picks((messy, "Fits.")), CANDIDATES)
    assert [p.isbn13 for p in result] == [ISBN_1]


def test_duplicates_and_empty_reasons_are_dropped() -> None:
    result = clean_picks(
        picks((ISBN_1, "First."), (ISBN_1, "Again."), (ISBN_2, "   "), (ISBN_3, "Ok.")),
        CANDIDATES,
    )
    assert [(p.isbn13, p.rank, p.reason) for p in result] == [
        (ISBN_1, 1, "First."),
        (ISBN_3, 2, "Ok."),
    ]


def test_at_most_10_picks() -> None:
    many = [book(n) for n in range(15)]
    result = clean_picks(picks(*((b.isbn13, "Fits.") for b in many)), many)
    assert len(result) == MAX_PICKS
    assert result[-1].rank == MAX_PICKS
