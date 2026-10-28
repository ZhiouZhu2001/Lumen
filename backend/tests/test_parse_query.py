from app.graph.parse_query import MAX_SEARCHES, ParsedQuery, clean_parsed_query

QUERY = "quiero una novela triste sobre el mar"


def clean(searches: list[str], genre: str | None = None) -> ParsedQuery:
    return clean_parsed_query(ParsedQuery(searches=searches, genre=genre), QUERY)


def test_good_output_is_kept() -> None:
    result = clean(["novela mar", "naufragio"], "literary fiction")
    assert result.searches == ["novela mar", "naufragio"]
    assert result.genre == "literary fiction"


def test_searches_are_trimmed_and_spaces_collapsed() -> None:
    assert clean(["  novela   del  mar "]).searches == ["novela del mar"]


def test_empty_and_duplicate_searches_are_dropped() -> None:
    result = clean(["mar", "", "   ", "Mar", "MAR", "naufragio"])
    assert result.searches == ["mar", "naufragio"]


def test_at_most_three_searches() -> None:
    result = clean(["a1", "b2", "c3", "d4", "e5"])
    assert len(result.searches) == MAX_SEARCHES
    assert result.searches == ["a1", "b2", "c3"]


def test_falls_back_to_the_readers_words() -> None:
    assert clean([]).searches == [QUERY]
    assert clean(["", "  "]).searches == [QUERY]


def test_genre_is_normalized() -> None:
    assert clean(["mar"], "  Thriller ").genre == "thriller"
    assert clean(["mar"], "   ").genre is None
    assert clean(["mar"], None).genre is None
