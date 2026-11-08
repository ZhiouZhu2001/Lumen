import re
import unicodedata
from urllib.parse import urlsplit

from app.sources.schemas import BookCandidate


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"[^\W_]+", text))


def title_key(value: str) -> str:
    # Compare works; a subtitle may differ between editions. Keep volume numbers.
    return normalize(re.split(r"[:;]", value, maxsplit=1)[0])


def author_tokens(value: str) -> set[str]:
    return set(normalize(value).split()) - {"de", "del", "la", "el", "the", "and"}


def matches_work(book: BookCandidate, title: str, authors: list[str]) -> bool:
    original, actual_title = normalize(book.title), normalize(title)
    if not original or not actual_title:
        return False
    # Do not merge two different subtitles or numbered volumes.
    if original != actual_title and (
        title_key(book.title) != title_key(title)
        or (original != title_key(book.title) and actual_title != title_key(title))
        or re.search(
            r"\b(?:vol(?:ume)?|part|tomo|book|no)\s*\d+\b",
            original + " " + actual_title,
        )
    ):
        return False
    for expected in book.authors:
        a = author_tokens(expected)
        for actual in authors:
            b = author_tokens(actual)
            if (
                a
                and b
                and (a == b or (min(len(a), len(b)) >= 2 and (a <= b or b <= a)))
            ):
                return True
    return False


def safe_url(value: str, host: str, *, upgrade_http: bool = False) -> str | None:
    try:
        parsed = urlsplit(value)
        if parsed.scheme == "http" and upgrade_http:
            parsed = parsed._replace(scheme="https")
        actual = parsed.hostname or ""
        if (
            parsed.scheme == "https"
            and (actual == host or actual.endswith("." + host))
            and not parsed.username
            and not parsed.password
            and parsed.port in (None, 443)
        ):
            return parsed.geturl()
    except ValueError:
        return None
    return None
