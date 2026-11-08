from copy import deepcopy

import pytest

from app.channels.matching import matches_work
from app.channels.rules import StoreRule, StoreRules, load_rules
from app.sources.apple_books import parse_apple_books
from app.sources.gutendex import parse_gutendex
from tests.test_book_cards import book, fixture


@pytest.mark.parametrize(
    "defect", ["author", "language", "copyright", "media", "url", "identifier"]
)
def test_gutenberg_requires_matching_work_language_rights_and_download(defect):
    data = deepcopy(fixture("gutendex"))
    row = data["results"][0]
    if defect == "author":
        row["authors"] = [{"name": "Different Person"}]
    elif defect == "language":
        row["languages"] = ["fr"]
    elif defect == "copyright":
        row["copyright"] = None
    elif defect == "media":
        row["media_type"] = "Sound"
    elif defect == "url":
        row["formats"] = {
            "text/html": "https://gutenberg.org.evil.test/ebooks/1342.html"
        }
    else:
        row["id"] = 11
    assert parse_gutendex(data, book()) is None


@pytest.mark.parametrize("defect", ["author", "country", "kind", "url", "identifier"])
def test_apple_requires_ebook_work_and_spanish_storefront(defect):
    data = {"results": [deepcopy(fixture("apple")["results"][0])]}
    row = data["results"][0]
    if defect == "author":
        row["artistName"] = "Another Author"
    elif defect == "country":
        row["trackViewUrl"] = row["trackViewUrl"].replace("/es/", "/us/")
    elif defect == "kind":
        row["kind"] = "audiobook"
    elif defect == "url":
        row["trackViewUrl"] = "https://books.apple.com.evil.test/es/book/id395534643"
    else:
        row["trackId"] = 1
    assert parse_apple_books(data, book()) is None


@pytest.mark.parametrize(
    ("title", "authors", "expected"),
    [
        ("Pride and Prejudice", ["Austen, Jane"], True),
        ("Pride and Prejudice: An illustrated edition", ["Jane Austen"], True),
        ("Pride and Prejudice Volume 2", ["Jane Austen"], False),
        ("Pride and Prejudice", ["Austen"], False),
        ("Pride and Prejudice", ["Mina Austen"], False),
    ],
)
def test_matching_is_conservative_about_titles_and_author_identity(
    title, authors, expected
):
    assert matches_work(book(), title, authors) is expected


def test_different_subtitles_do_not_share_a_work_match():
    assert not matches_work(
        book(title="Selected Works: One"), "Selected Works: Two", ["Jane Austen"]
    )


@pytest.mark.parametrize(
    "change",
    [
        {"url_template": "http://www.amazon.es/s?k={isbn13}"},
        {"url_template": "https://example.test/?isbn={isbn13}"},
        {"url_template": "https://www.amazon.es/s?k={isbn13.__class__}"},
        {"url_template": "https://www.amazon.es/s?k={isbn13:999}"},
    ],
)
def test_unsafe_or_invalid_templates_fail_configuration(change):
    data = load_rules()[0].model_dump()
    data.update(change)
    with pytest.raises(ValueError):
        StoreRule.model_validate(data)


def test_duplicate_stores_fail_configuration():
    rule = load_rules()[0]
    with pytest.raises(ValueError, match="unique"):
        StoreRules(stores=[rule, rule])
