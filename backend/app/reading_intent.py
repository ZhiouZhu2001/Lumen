"""Reject clear language-course substitutions for literary reading requests."""

import re

from app.channels.matching import normalize
from app.sources.schemas import BookCandidate

COURSE_MARKERS = (
    "foreign language study",
    "language and languages study and teaching",
    "language learning",
    "language learners",
    "learn spanish",
    "learning spanish",
    "learn english",
    "learning english",
    "learn french",
    "learning french",
    "learn german",
    "learn portuguese",
    "learn italian",
    "learn japanese",
    "learn to speak",
    "build your vocabulary",
    "improve your vocabulary",
    "reading comprehension exercises",
    "aprender espanol",
    "aprender ingles",
    "aprende espanol",
    "aprende ingles",
    "estudiantes de idiomas",
    "learn the language",
    "language practice",
    "questionnaire section",
    "vocabulary",
)


def concedes_mismatch(reason: str, query: str) -> bool:
    """Reject explicit concessions about requested terms, not arbitrary negation."""
    terms = {word for word in normalize(query).split() if len(word) >= 3}
    pattern = r"\b(?:although|though|even though|while)\s+(?:it|this book|this novel|the book|the novel)(?:\s+(?:is|does)\s+not|'s\s+not|\s+isn't|\s+doesn't)\b[^.!?;,]{0,100}|\b(?:although not|though not|aunque no|aun sin|pese a no)\b[^.!?;,]{0,100}"
    for clause in re.findall(pattern, reason, flags=re.IGNORECASE):
        normalized = normalize(clause)
        if "no solo" in normalized or "not only" in normalized:
            continue
        if terms.intersection(normalized.split()):
            return True
    return False


def matches_reader_type(book: BookCandidate, query: str, genre: str | None) -> bool:
    literary = {
        "fiction",
        "story",
        "stories",
        "novel",
        "novels",
        "thriller",
        "fantasy",
        "mystery",
        "manga",
    }
    if not literary.intersection(normalize(genre or "").split()):
        return True
    wish = normalize(query)
    if re.search(
        r"\b(language|languages|idioma|idiomas|vocabulary|grammar|vocabulario|gramatica)\b",
        wish,
    ) or any(marker in wish for marker in COURSE_MARKERS):
        return True
    categories = normalize(" ".join(book.genres))
    if any(marker in categories for marker in COURSE_MARKERS[:2]):
        return False
    # An explicitly graded reader is educational even without a full synopsis.
    if "for beginners" in normalize(book.title) and re.search(
        r"\b(spanish|english|french|german|portuguese|italian|japanese)\b",
        normalize(book.title),
    ):
        return False
    description = normalize(book.description or "")
    return sum(marker in description for marker in COURSE_MARKERS[2:]) < 2
