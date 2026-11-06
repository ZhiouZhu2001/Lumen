"""Shared lightweight grounding checks for production and evaluation."""

import re
import unicodedata


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
