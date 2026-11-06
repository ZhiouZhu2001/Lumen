import pytest
from langgraph.graph import END

from app.graph.rank import Pick
from app.graph.state import MAX_RETRIES, MIN_PICKS, SearchState, route_after_ranking


@pytest.mark.parametrize(
    ("pick_count", "retries", "expected"),
    [
        (5, 0, END),
        (10, 0, END),
        (5, MAX_RETRIES, END),
        (4, 0, "broaden"),
        (0, 0, "broaden"),
        (3, MAX_RETRIES - 1, "broaden"),
        (0, MAX_RETRIES, END),
        (3, MAX_RETRIES, END),
    ],
)
def test_only_validated_recommendations_control_the_single_branch(
    pick_count, retries, expected
):
    state = SearchState(
        query="novela",
        language="es",
        parsed=None,
        tried=[],
        candidates=[],
        retries=retries,
        picks=[
            Pick(isbn13=str(n), rank=n + 1, reason="Validated upstream.")
            for n in range(pick_count)
        ],
    )
    assert route_after_ranking(state) == expected
    assert MIN_PICKS == 5
