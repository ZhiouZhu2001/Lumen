import pytest
from langgraph.graph import END

from app.graph.state import MAX_RETRIES, MIN_CANDIDATES, SearchState, route_after_search
from app.sources.schemas import BookCandidate


def book(n: int, description: str | None = "A novel.") -> BookCandidate:
    return BookCandidate(
        isbn13=f"978{n:010d}",
        title=f"Book {n}",
        language="es",
        description=description,
        source="google_books",
    )


def state(candidates: list[BookCandidate], retries: int) -> SearchState:
    return SearchState(
        query="novela",
        language="es",
        parsed=None,
        tried=[],
        candidates=candidates,
        retries=retries,
        picks=[],
    )


ENOUGH = [book(n) for n in range(MIN_CANDIDATES)]
TOO_FEW = ENOUGH[:3]


@pytest.mark.parametrize(
    ("candidates", "retries", "expected"),
    [
        (ENOUGH, 0, "rank_and_explain"),  # enough on the first try
        (TOO_FEW, 0, "broaden"),  # too few: retry
        (TOO_FEW, MAX_RETRIES - 1, "broaden"),  # still a retry left
        (TOO_FEW, MAX_RETRIES, "rank_and_explain"),  # out of retries: use what we have
        ([], 0, "broaden"),
        ([], MAX_RETRIES, END),  # nothing at all after 2 retries: no_results
    ],
)
def test_route_after_search(candidates, retries, expected) -> None:
    assert route_after_search(state(candidates, retries)) == expected


def test_books_without_a_description_do_not_count() -> None:
    no_descriptions = [book(n, None) for n in range(50)]
    assert route_after_search(state(no_descriptions, 0)) == "broaden"
    assert route_after_search(state(no_descriptions, MAX_RETRIES)) == END


@pytest.mark.parametrize(
    ("count", "expected"),
    [(4, "broaden"), (5, "rank_and_explain"), (9, "rank_and_explain")],
)
def test_specification_threshold_is_five_rankable_books(count, expected) -> None:
    assert route_after_search(state([book(n) for n in range(count)], 0)) == expected


def test_whitespace_descriptions_do_not_satisfy_the_threshold() -> None:
    assert (
        route_after_search(state([book(n, " \n ") for n in range(10)], 0)) == "broaden"
    )
