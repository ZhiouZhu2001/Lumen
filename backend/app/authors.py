"""Literal reader author requirements, checked against catalog author metadata."""

import re
import unicodedata

from app.sources.schemas import BookCandidate


def name_words(value: str) -> tuple[str, ...]:
    text = unicodedata.normalize("NFKD", value.casefold())
    return tuple(
        re.findall(r"[^\W_]+", "".join(c for c in text if not unicodedata.combining(c)))
    )


def mentioned(query: str, name: str) -> bool:
    words, wanted = name_words(query), name_words(name)
    return bool(wanted) and any(
        words[i : i + len(wanted)] == wanted for i in range(len(words))
    )


def excluded_reference(query: str, name: str) -> bool:
    words, wanted = name_words(query), name_words(name)
    topical = {"about", "sobre", "like", "como", "unlike", "except", "excepto", "salvo"}
    blocked = topical | {
        "not",
        "no",
        "excluding",
        "menos",
        "similar",
        "estilo",
        "vida",
        "life",
        "biography",
        "biografia",
    }
    for i in range(len(words)):
        if words[i : i + len(wanted)] != wanted or i == 0:
            continue
        if words[i - 1] in topical:
            return True
        if words[i - 1] in {"by", "de", "por", "of"} and blocked.intersection(
            words[max(0, i - 3) : i - 1]
        ):
            return True
    return False


def clean_requested_authors(query: str, names: list[str]) -> list[str]:
    result = []
    generic = {
        "author",
        "authors",
        "autor",
        "autora",
        "autores",
        "autoras",
        "spanish",
        "espanol",
        "espanola",
        "english",
        "british",
        "french",
        "frances",
        "spain",
        "espana",
    }
    for value in names:
        name = " ".join(value.split())
        tokens = name_words(name)
        if (
            not tokens
            or len(name) > 100
            or not any(c.isalpha() for c in name)
            or (len(tokens) == 1 and generic.intersection(tokens))
            or {
                "author",
                "authors",
                "autor",
                "autora",
                "autores",
                "autoras",
                "writer",
                "writers",
                "escritor",
                "escritora",
            }.intersection(tokens)
            or not mentioned(query, name)
            or excluded_reference(query, name)
        ):
            continue
        if tokens not in {name_words(previous) for previous in result}:
            result.append(name)
    return result[:5]


def known_requested_authors(query: str, candidates: list[BookCandidate]) -> list[str]:
    """Recover narrow by/de attributions to real, literally named catalog authors.

    This also protects old captured snapshots without the new parsed field.
    Topic, comparison and negative mentions do not establish authorship.
    """
    words = name_words(query)
    blocked = {
        "not",
        "except",
        "excluding",
        "excepto",
        "salvo",
        "menos",
        "no",
        "like",
        "similar",
        "como",
        "estilo",
        "vida",
        "life",
        "biography",
        "biografia",
    }
    found = []
    for book in candidates:
        for author in book.authors:
            tokens = name_words(author)
            if len(tokens) < 2:
                continue
            for i in range(1, len(words)):
                if words[i : i + len(tokens)] != tokens:
                    continue
                prefix = words[:i]
                if prefix[-1] not in {"by", "de", "por"}:
                    continue
                if blocked.intersection(prefix[max(0, len(prefix) - 4) : -1]):
                    continue
                found.append(author)
    return clean_requested_authors(query, found)


def matches_authors(book: BookCandidate, requested: list[str]) -> bool:
    if not requested:
        return True
    for author in book.authors:
        forms = {name_words(author)}
        if author.count(",") == 1:
            last, first = author.split(",", 1)
            forms.add(name_words(first + " " + last))
        for name in requested:
            forms_for_name = {name_words(name)}
            if name.count(",") == 1:
                last, first = name.split(",", 1)
                forms_for_name.add(name_words(first + " " + last))
            if forms.intersection(forms_for_name):
                return True
    return False


def anchor_searches(searches: list[str], requested: list[str]) -> list[str]:
    if len(requested) != 1:
        return searches
    name = requested[0]
    return list(
        dict.fromkeys(
            query if mentioned(query, name) else f"{query} {name}" for query in searches
        )
    )
