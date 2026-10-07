DIGITS = "0123456789"


def isbn13_check_digit(first12: str) -> str:
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(first12))
    return str((10 - total % 10) % 10)


def is_valid_isbn10(isbn: str) -> bool:
    """Check if isbn is a valid isbn10 format"""
    if len(isbn) != 10:
        return False

    if any(c not in DIGITS for c in isbn[:9]):
        return False

    last = isbn[9].upper()
    if last not in DIGITS and last != "X":
        return False

    values = [int(c) for c in isbn[:9]] + [10 if last == "X" else int(last)]

    total = sum(v * w for v, w in zip(values, range(10, 0, -1)))
    return total % 11 == 0


def to_isbn13(raw: str) -> str | None:
    """Return a valid ISBN-13 for an ISBN-10 or ISBN-13 string, or None.
    Hyphens and spaces are ignored. Invalid check digits return None.
    """
    isbn = raw.replace("-", "").replace(" ", "")

    if len(isbn) == 13:
        if any(c not in DIGITS for c in isbn):
            return None
        return isbn if isbn13_check_digit(isbn[:12]) == isbn[12] else None

    if len(isbn) == 10:
        if not is_valid_isbn10(isbn):
            return None
        first12 = "978" + isbn[:9]
        return first12 + isbn13_check_digit(first12)

    return None
