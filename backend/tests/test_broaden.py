from app.graph.broaden import drop_tried_searches
from app.graph.parse_query import ParsedQuery

TRIED = ["novela Guerra Civil española", "novela amor Guerra Civil"]


def broadened(*searches: str) -> ParsedQuery:
    return drop_tried_searches(
        ParsedQuery(searches=list(searches), genre="historical fiction"), TRIED
    )


def test_new_searches_are_kept() -> None:
    result = broadened("novela histórica España", "novela posguerra")
    assert result.searches == ["novela histórica España", "novela posguerra"]
    assert result.genre == "historical fiction"


def test_searches_already_tried_are_dropped_ignoring_case() -> None:
    result = broadened("Novela Amor Guerra Civil", "novela posguerra")
    assert result.searches == ["novela posguerra"]


def test_nothing_new_gives_an_empty_list() -> None:
    assert broadened("novela guerra civil española").searches == []
