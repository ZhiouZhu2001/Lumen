import json
from pathlib import Path

import pytest

from app.graph.rank import select_for_ranking
from app.grounding import description_evidence
from app.reading_intent import concedes_mismatch, matches_reader_type
from app.sources.schemas import BookCandidate

RECORDS = json.loads(
    (Path(__file__).parent / "fixtures/reading_type_followup_update25.json").read_text(
        "utf-8"
    )
)["records"]


@pytest.mark.parametrize(
    "record",
    [r for r in RECORDS if r["candidate"]["isbn13"] != "9781340139742"],
    ids=lambda record: record["candidate"]["isbn13"],
)
def test_real_commentary_essays_and_expedition_accounts_cannot_replace_narratives(
    record,
):
    assert not matches_reader_type(
        BookCandidate.model_validate(record["candidate"]),
        record["query"],
        record["genre"],
    )


def test_publisher_only_description_cannot_supply_grounding_for_ranking():
    record = next(r for r in RECORDS if r["candidate"]["isbn13"] == "9781340139742")
    assert not select_for_ranking([BookCandidate.model_validate(record["candidate"])])


@pytest.mark.parametrize(
    "text",
    [
        "<p>This work has been selected by scholars as being important.</p>",
        "&lt;p&gt;This work has been selected by scholars as being important.&lt;/p&gt;",
        "This work is in the public domain in the United States.",
    ],
)
def test_markup_and_copyright_only_text_are_not_book_specific_evidence(text):
    assert description_evidence(text) == ""


def test_real_blurb_is_retained_without_publisher_tail_or_mutating_the_snapshot():
    from tests.test_rank import book

    original = "<p>A novel about a voyage by Fuß.</p> About the publisher: Forgotten Books publishes rare books."
    candidate = book(1, original)
    assert description_evidence(original) == "A novel about a voyage by Fuß."
    assert select_for_ranking([candidate]) == [candidate]
    assert candidate.description == original


def test_genuine_philosophical_fiction_and_requested_commentary_remain_eligible():
    from tests.test_rank import book

    candidate = book(
        1, "A philosophical novel about a sailor examining ethics."
    ).model_copy(update={"genres": ["Fiction", "Philosophy"]})
    assert matches_reader_type(candidate, "A philosophical novel", "literary fiction")
    commentary = BookCandidate.model_validate(RECORDS[0]["candidate"])
    assert matches_reader_type(
        commentary, "An introduction to superhero ethics", "nonfiction"
    )


@pytest.mark.parametrize(
    "record",
    json.loads(
        (Path(__file__).parent / "fixtures/travel_mismatches_update25.json").read_text(
            "utf-8"
        )
    )["records"],
    ids=lambda record: record["candidate"]["isbn13"],
)
def test_real_travel_guides_and_travel_writing_do_not_satisfy_a_novel_request(record):
    assert not matches_reader_type(
        BookCandidate.model_validate(record["candidate"]),
        record["query"],
        record["genre"],
    )


def test_a_travel_novel_and_a_requested_travel_guide_are_distinguished():
    from tests.test_rank import book

    novel = book(1, "A novel about a journey through mountains.").model_copy(
        update={"genres": ["Travel"]}
    )
    assert matches_reader_type(novel, "An adventure novel", "adventure fiction")
    guide = BookCandidate.model_validate(
        json.loads(
            (
                Path(__file__).parent / "fixtures/travel_mismatches_update25.json"
            ).read_text("utf-8")
        )["records"][-1]["candidate"]
    )
    assert matches_reader_type(guide, "A guide to adventure travel", "travel")


@pytest.mark.parametrize(
    "reason",
    [
        "It is a comic-strip collection, but the catalog text does not mention superheroes or moral dilemmas.",
        "La sinopsis no menciona superhéroes ni dilemas morales.",
    ],
)
def test_catalog_concessions_cannot_hide_absent_requested_subjects(reason):
    assert concedes_mismatch(
        reason, "Graphic novels about superheroes and moral dilemmas"
    )


def test_an_in_story_negation_is_not_a_catalog_concession():
    assert not concedes_mismatch(
        "The hero does not mention his secret identity. It explores moral dilemmas.",
        "Graphic novels about superheroes and moral dilemmas",
    )


def test_a_critical_compilation_is_distinguished_from_graphic_fiction():
    from tests.test_rank import book

    commentary = book(
        1,
        "A landmark critical compilation introduces readers to award-winning comics. "
        "Each story has an introduction and annotations.",
    ).model_copy(update={"genres": ["Comics & Graphic Novels"]})
    assert not matches_reader_type(
        commentary, "Graphic novels about superheroes", "graphic novels"
    )
    assert matches_reader_type(
        commentary, "A critical compilation about comics", "nonfiction"
    )


@pytest.mark.parametrize(
    ("genres", "description"),
    [
        (
            ["Comics & Graphic Novels"],
            "A journalist returns to a city changed by technology.",
        ),
        (
            ["Fiction", "Superheroes"],
            "A young warrior longs to prove herself to her sisters.",
        ),
        (["Humor"], "The adventures of a child and his stuffed tiger."),
    ],
)
def test_explicit_superhero_graphic_requests_need_evidence_for_both_requirements(
    genres, description
):
    from tests.test_rank import book

    candidate = book(1, description).model_copy(update={"genres": genres})
    assert not matches_reader_type(
        candidate,
        "Graphic novels about superheroes and moral dilemmas",
        "graphic novels",
    )


def test_superhero_graphic_evidence_preserves_actual_matches_and_exclusions():
    from tests.test_rank import book

    candidate = book(1, "A superhero weighs loyalty against duty.").model_copy(
        update={"genres": ["Graphic novels", "Superheroes"]}
    )
    assert matches_reader_type(
        candidate, "Graphic novels about superheroes", "graphic novels"
    )
    ordinary = candidate.model_copy(
        update={
            "description": "A graphic novel about friendship.",
            "genres": ["Graphic novels"],
        }
    )
    assert matches_reader_type(
        ordinary, "Graphic novels without superheroes", "graphic novels"
    )
