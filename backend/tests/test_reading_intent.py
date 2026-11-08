import pytest

from app.reading_intent import concedes_mismatch, matches_reader_type
from tests.test_workflow import book


@pytest.mark.parametrize(
    "changes",
    [
        {"title": "Spanish Short Stories for Beginners"},
        {"genres": ["Foreign Language Study"]},
        {"description": "Learn Spanish through stories and build your vocabulary."},
        {"genres": ["Language and languages, study and teaching"]},
    ],
)
def test_language_courses_cannot_replace_literary_collections(changes):
    candidate = book(0).model_copy(update=changes)
    assert not matches_reader_type(
        candidate, "Stories by authors from Spain", "short stories"
    )


def test_language_practice_remains_available_when_explicitly_requested():
    candidate = book(0).model_copy(update={"genres": ["Foreign Language Study"]})
    assert matches_reader_type(
        candidate, "Learn Spanish through short stories", "short stories"
    )
    assert matches_reader_type(
        candidate, "Quiero cuentos para practicar idiomas", "short stories"
    )


def test_beginner_astronomy_and_ordinary_literature_are_not_courses():
    candidate = book(0).model_copy(update={"title": "Astronomy for Beginners"})
    assert matches_reader_type(candidate, "Beginner astronomy", "popular science")
    assert matches_reader_type(book(0), "A literary sea story", "literary fiction")


@pytest.mark.parametrize(
    "reason",
    [
        "Es una novela triste, aunque no esté centrada en el mar.",
        "Aunque no es mar, es una historia triste sobre un río.",
        "Although it is not about the sea, it has a sad atmosphere.",
        "Though it's not set at sea, it is a sad novel.",
    ],
)
def test_explicit_admissions_do_not_satisfy_the_requested_subject(reason):
    assert concedes_mismatch(
        reason, "Quiero una novela triste sobre el mar. A sad novel about the sea."
    )


@pytest.mark.parametrize(
    "reason",
    [
        "A sea story in which no one knows the ending.",
        "Aunque no solo trata del mar, este es el centro del relato.",
        "Although it is not only about the sea, the voyage is central.",
        "It is a sad novel about the sea.",
    ],
)
def test_ordinary_negation_and_positive_not_only_are_not_missing_requirements(reason):
    assert not concedes_mismatch(reason, "Una novela sobre el mar. A sea novel.")
