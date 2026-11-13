"""Shared lightweight grounding checks for production and evaluation."""

import re
import unicodedata
from html import unescape

PUBLISHER_BOILERPLATE = (
    "this work has been selected by scholars",
    "this work was reproduced from the original artifact",
    "about the publisher",
    "forgotten books publishes",
    "this book is a reproduction of",
    "this is a reproduction of a book published before",
    "this work is in the public domain",
    "as a reproduction of a historical artifact",
    "we appreciate your support of the preservation process",
    "find more at www.forgottenbooks.com",
)
_PUBLISHER_PATTERN = re.compile(
    "|".join(re.escape(marker) for marker in PUBLISHER_BOILERPLATE), re.IGNORECASE
)


def description_evidence(description: str | None) -> str:
    """Keep book-specific text without altering the original catalog snapshot."""
    text = re.sub(r"<[^>]+>", " ", unescape(description or ""))
    boundary = _PUBLISHER_PATTERN.search(text)
    if boundary:
        text = text[: boundary.start()]
    return " ".join(text.split()).strip()


def words(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text).casefold()
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return set(re.findall(r"[^\W\d_]+", normalized))


def unknown_proper_words(reason: str, allowed: str) -> list[str]:
    """Heuristic only: skip sentence-initial words, inspect other capitalized words."""
    permitted = words(allowed)
    unknown = set()
    for sentence in re.split(r"(?<=[.!?])\s+", reason.strip()):
        tokens = re.findall(r"[^\W\d_]+", sentence)
        for token in tokens[1:]:
            if token != "I" and token[0].isupper() and not words(token) <= permitted:
                unknown.add(token)
    return sorted(unknown)
