from app.graph.rank import (
    MAX_CANDIDATES,
    MAX_DESCRIPTION_CHARS,
    MAX_PICKS,
    ModelPick,
    ModelPicks,
    clean_picks,
    format_candidates,
    select_for_ranking,
    validate_picks,
)
from app.sources.isbn import isbn13_check_digit
from app.sources.schemas import BookCandidate


def book(n: int, description: str | None = "A novel.") -> BookCandidate:
    first12 = f"97884{n:07d}"
    return BookCandidate(
        isbn13=first12 + isbn13_check_digit(first12),
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
    books = [book(1, None), book(2), book(3, ""), book(4), book(5, " \n\t ")]
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


def test_wrong_language_and_unsupported_names_are_rejected_without_losing_good_picks():
    output = picks(
        (ISBN_1, "A trip to Atlantis."), (ISBN_2, "Fits."), (ISBN_3, "Fits.")
    )
    candidates = [*CANDIDATES[:2], CANDIDATES[2].model_copy(update={"language": "en"})]
    result, feedback = validate_picks(output, candidates, "es")
    assert [p.isbn13 for p in result] == [ISBN_2]
    assert any("Atlantis" in item for item in feedback)
    assert any("wrong book language" in item for item in feedback)


def test_only_spaces_and_hyphens_are_normalized_in_isbns():
    bad = picks(("978" + ISBN_1, "Fits."), (ISBN_1 + "abc", "Fits."), (ISBN_2, "Fits."))
    assert [p.isbn13 for p in clean_picks(bad, CANDIDATES)] == [ISBN_2]


def test_retained_and_new_books_take_precedence_without_exceeding_thirty():
    books = [book(n) for n in range(40)]
    selected = select_for_ranking(
        books, priority_isbns=[books[3].isbn13, books[-1].isbn13], language="es"
    )
    assert len(selected) == 30
    assert [b.isbn13 for b in selected[:2]] == [books[3].isbn13, books[-1].isbn13]


def test_author_field_alone_does_not_justify_a_name_in_the_reason():
    output = picks((ISBN_1, "A story by Ana García."))
    result, feedback = validate_picks(output, CANDIDATES, "es")
    assert result == []
    assert any("Ana" in issue and "García" in issue for issue in feedback)
    supported = CANDIDATES[0].model_copy(
        update={"description": "A novel by Ana García."}
    )
    assert len(validate_picks(output, [supported], "es")[0]) == 1


async def test_manual_runner_reads_validated_attempt_without_starting_network(
    monkeypatch, capsys
):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from app.graph.parse_query import ParsedQuery
    from app.graph.rank import Pick, RankingAttempt
    from scripts import try_rank

    @asynccontextmanager
    async def client():
        yield object()

    attempt = RankingAttempt(
        [Pick(isbn13=ISBN_1, rank=1, reason="Fits.")],
        ["A rejected reason."],
        CANDIDATES,
        [],
        True,
    )
    monkeypatch.setattr(
        try_rank, "get_settings", lambda: SimpleNamespace(google_books_api_key=None)
    )
    monkeypatch.setattr(try_rank, "diagnostic_model", client)
    monkeypatch.setattr(try_rank, "make_http_client", client)
    monkeypatch.setattr(
        try_rank,
        "parse_query",
        AsyncMock(return_value=ParsedQuery(searches=["novela mar"], genre=None)),
    )
    monkeypatch.setattr(
        try_rank, "search_candidates", AsyncMock(return_value=CANDIDATES)
    )
    monkeypatch.setattr(try_rank, "rank_and_explain", AsyncMock(return_value=attempt))
    await try_rank.main()
    output = capsys.readouterr().out
    assert ISBN_1 in output
    assert "Validation feedback:" in output
