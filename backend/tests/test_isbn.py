import pytest

from app.sources.isbn import to_isbn13


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9780307474728", "9780307474728"),  # valid ISBN-13 stays the same
        ("978-0-307-47472-8", "9780307474728"),  # hyphens are ignored
        (" 9780307474728 ", "9780307474728"),  # surrounding spaces are ignored
        ("0307474720", "9780307474728"),  # ISBN-10 is converted
        ("843760494X", "9788437604947"),  # ISBN-10 ending in X
        ("843760494x", "9788437604947"),  # lowercase x too
    ],
)
def test_valid_isbns_become_isbn13(raw: str, expected: str) -> None:
    assert to_isbn13(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "9780307474729",  # ISBN-13 with wrong check digit
        "0307474721",  # ISBN-10 with wrong check digit
        "03074747X6",  # checksum would pass, but X is only allowed last
        "97803074747",  # wrong length
        "UOM:39015012345678",  # not an ISBN
        "",
    ],
)
def test_invalid_isbns_return_none(raw: str) -> None:
    assert to_isbn13(raw) is None
