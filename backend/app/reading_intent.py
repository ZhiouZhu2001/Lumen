"""Reject explicit reading-form substitutions; ambiguous metadata stays eligible."""

import re

from app.channels.matching import normalize
from app.grounding import description_evidence
from app.sources.schemas import BookCandidate, Language

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

FICTION_FORMS = r"\b(?:fiction|ficcion|novels?|novelas?|novellas?|stories|story|cuentos?|relatos?)\b"
ACTIVITY_FORMS = r"\b(?:colou?ring books?|libros? (?:de|para) colorear|activity books?|workbooks?|cuadernos? de actividades|libros? de ejercicios)\b"
SUPERHERO_FORM = r"\bsuper ?hero(?:e?s|e|ines?)?\b"
GRAPHIC_FORM = r"\b(?:comics?|comic books?|graphic novels?|novelas? graficas?|historietas?|tebeos?|manga)\b"


def explicit_superhero_request(query: str) -> bool:
    wish = normalize(query)
    return bool(re.search(SUPERHERO_FORM, wish)) and not re.search(
        r"\b(?:not|without|excluding|no|sin|excepto|don t want|like|similar to|como)\s+(?:\w+\s+){0,2}super ?hero",
        wish,
    )


def anchor_subgenre_searches(
    query: str, searches: list[str], language: Language
) -> list[str]:
    """Preserve an explicit superhero subgenre; never infer titles or authors."""
    if not explicit_superhero_request(query):
        return searches
    form = "superhero" if language == "en" else "superhéroes"
    return [
        search if re.search(SUPERHERO_FORM, normalize(search)) else f"{search} {form}"
        for search in searches
    ]


def literary_request(query: str, genre: str | None) -> bool:
    wish = normalize(query)
    primary = re.split(r"\b(?:about|sobre|acerca de|on)\b", wish, maxsplit=1)[0]
    primary = re.sub(r"\b(?:non fiction|no ficcion)\b", "nonfiction", primary)
    if re.search(ACTIVITY_FORMS, primary) or re.search(
        r"\b(?:literary criticism|critica literaria|literary studies|estudios literarios|history of the novel|history of novels|historia de la novela)\b",
        primary,
    ):
        return False
    if re.search(FICTION_FORMS, primary):
        return True
    category = normalize(genre or "")
    if re.search(r"\b(?:nonfiction|non fiction|no ficcion)\b", category):
        return False
    return bool(
        re.search(
            r"\b(?:fiction|stories|novel|thriller|fantasy|mystery|manga|comic|comics|romance|horror|adventure)\b",
            category,
        )
    )


def fictional_metadata(book: BookCandidate) -> bool:
    categories = " ".join(
        normalize(genre)
        for genre in book.genres
        if not re.search(
            r"\b(?:nonfiction|non fiction|no ficcion|literary criticism|literary studies|critica literaria)\b",
            normalize(genre),
        )
    )
    return bool(
        re.search(FICTION_FORMS, categories)
        or re.search(r"\b(?:manga|comics|graphic novels|novela grafica)\b", categories)
        or re.search(
            r"^(?:a|an|this|una|esta) (?:(?:historical|literary|mystery|romantic|adventure|gothic|fantasy|graphic|classic|thrilling|sad|moving) )?(?:novel|novella|novela)\b",
            normalize(book.description or ""),
        )
    )


def clear_nonfiction(book: BookCandidate) -> bool:
    categories = normalize(" ".join(book.genres))
    description = normalize(description_evidence(book.description))
    # Describe this book's form, rather than accepting its subject's form.
    self_described_novel = re.search(
        r"^(?:a|an|this|una|esta) (?:(?:historical|literary|philosophical|mystery|romantic|adventure|gothic|fantasy|graphic|classic|thrilling|sad|moving) )?(?:novel|novella|novela)\b",
        description,
    )
    if not self_described_novel and (
        re.search(
            r"\b(?:essay from the year|this essay discusses|this dissertation|this study examines|philosophical lens|introduction to philosophical ethics|critical analysis of|critical compilation|compilacion critica)\b",
            description,
        )
        or re.search(r"\b(?:philosopher reads|filosofo lee)\b", normalize(book.title))
        or (
            re.search(r"\b(?:history|historia)\b", categories)
            and re.search(
                r"\b(?:expedition|expedicion|military|militar)\b", description
            )
            and re.search(
                r"\b(?:historic file|historical account|ancient account|firsthand account|primary source|relato historico|fuente primaria)\b",
                description,
            )
        )
    ):
        return True
    # Explicit fictional catalog classification is stronger than a title keyword.
    if fictional_metadata(book):
        return False
    if re.search(
        r"\b(?:nonfiction|non fiction|no ficcion|literary criticism|literary studies|critica literaria|travel|viajes)\b",
        categories,
    ):
        return True
    title = normalize(book.title)
    description = normalize(book.description or "")
    return bool(
        re.search(
            r"^(?:(?:the|a|an|short|brief|illustrated|official|una|un|la|el|breve) )*(?:history of|report of|report on|essays on|study of|historia de|informe de|ensayos sobre|estudio de)\b",
            title,
        )
        or re.search(
            r"\b(?:essays collected|collection of essays|coleccion de ensayos|ensayos reunidos|history of the novel|historia de la novela|literary criticism|critica literaria)\b",
            description,
        )
        or (
            re.search(r"\b(?:history|historia)\b", categories)
            and "historical work" in description
        )
    )


def concedes_mismatch(reason: str, query: str) -> bool:
    """Reject explicit concessions about requested terms, not arbitrary negation."""
    terms = {word for word in normalize(query).split() if len(word) >= 3}
    terms -= {
        "the",
        "and",
        "with",
        "about",
        "for",
        "want",
        "looking",
        "book",
        "books",
        "una",
        "las",
        "los",
        "del",
        "sobre",
        "para",
        "quiero",
        "libro",
        "libros",
        "que",
        "por",
        "con",
    }
    forms = {
        "novel",
        "novels",
        "novela",
        "novelas",
        "fiction",
        "ficcion",
        "story",
        "stories",
        "relatos",
        "cuentos",
    }
    if literary_request(query, None):
        terms.update(forms)
    else:
        terms -= forms
    patterns = (
        (
            r"\b(?:the (?:catalog|catalogue) text|the description|the synopsis)\s+"
            r"(?:does not|doesn't)\s+(?:mention|include|describe|feature)\b[^.!?;]{0,100}"
        ),
        (
            r"\b(?:la sinopsis|la descripcion|el texto del catalogo)\s+no\s+"
            r"(?:menciona|incluye|describe|presenta)\b[^.!?;]{0,100}"
        ),
        (
            r"\b(?:although|though|even though|while)\s+(?:it|this book|this novel|the book|the novel)"
            r"(?:\s+(?:is|does)\s+not|'s\s+not|\s+isn't|\s+doesn't)\b[^.!?;,]{0,100}"
        ),
        r"\b(?:although not|though not|aunque no|aun sin|pese a no)\b[^.!?;,]{0,100}",
        (
            r"\b(?:it|this book|this novel|the book|the novel|this volume)\s+is\s+"
            r"(?:(?!\b(?:who|that|which|where)\b)[^.!?;]){0,80}\b(?:not|rather than|instead of)\s+"
            r"(?:an? )?(?:novels?|fiction|stories|story|about|set|focused|centered|centred)\b[^.!?;]{0,100}"
        ),
        (
            r"\b(?:it|this book|this novel|the book|the novel)\s+isn['’]t\s+"
            r"(?:an? )?(?:novels?|fiction|stories|story|about|set)\b[^.!?;]{0,100}"
        ),
        (
            r"\b(?:it|this book|the book|this novel|the novel)\s+(?:does not|doesn't|cannot)\s+"
            r"(?:fully |quite )?(?:match|fit|meet|satisfy|contain|include|feature|take place|focus)\b[^.!?;]{0,100}"
        ),
        (
            r"\b(?:este libro|el libro|esta novela|la novela|este volumen)\s+"
            r"(?:no es|no cumple|no encaja|no se ajusta)\b[^.!?;]{0,100}"
        ),
        (
            r"\b(?:este libro|el libro|esta novela|la novela|este volumen)\s+es\s+[^.!?;]{0,80}"
            r"\b(?:no|en lugar de)\s+(?:un |una )?(?:novelas?|ficcion|relatos?|cuentos?)\b[^.!?;]{0,100}"
        ),
    )
    for clause in re.findall("|".join(patterns), reason, flags=re.IGNORECASE):
        normalized = normalize(clause)
        if "no solo" in normalized or "not only" in normalized:
            continue
        missing = re.split(
            r"\b(?:not|isn['’]t|doesn['’]t|rather than|instead of|no es|no cumple|no encaja|no se ajusta|no|en lugar de)\b",
            clause,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[-1]
        missing = normalize(re.split(r"[,;]", missing, maxsplit=1)[0])
        if terms.intersection(missing.split()):
            return True
    return False


def matches_reader_type(
    book: BookCandidate,
    query: str,
    genre: str | None,
    *,
    allow_missing_description: bool = False,
) -> bool:
    if not literary_request(query, genre):
        return True
    title = normalize(book.title)
    if not fictional_metadata(book) and re.search(
        ACTIVITY_FORMS, title + " " + normalize(book.description or "")
    ):
        return False
    if clear_nonfiction(book):
        return False
    wish = normalize(query)
    primary = re.split(r"\b(?:about|sobre|acerca de|on)\b", wish, maxsplit=1)[0]
    if (
        explicit_superhero_request(query)
        and re.search(GRAPHIC_FORM, primary + " " + normalize(genre or ""))
        and not (
            allow_missing_description and not description_evidence(book.description)
        )
    ):
        evidence = normalize(
            " ".join([book.title, *book.genres, description_evidence(book.description)])
        )
        if not re.search(GRAPHIC_FORM, evidence):
            return False
        if not re.search(SUPERHERO_FORM, evidence):
            return False
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
