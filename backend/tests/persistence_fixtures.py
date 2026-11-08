"""Recorded catalog input for persistence tests, with no external API requests."""

import json
from pathlib import Path

from app.channels.rules import load_rules, search_links
from app.channels.schemas import BookCard
from app.filters import SearchFilters
from app.graph.parse_query import ParsedQuery
from app.graph.rank import Pick
from app.graph.state import SearchState
from app.sources.google_books import parse_google_books


def completed(count=2):
    path = Path(__file__).parent / "fixtures/google_books_real_es.json"
    candidates = [
        b
        for b in parse_google_books(json.loads(path.read_text("utf-8")), "es")
        if b.description
    ]
    picks = [
        Pick(
            isbn13=b.isbn13,
            rank=i + 1,
            reason="Una lectura con datos del catálogo. Puedes consultar los detalles.",
        )
        for i, b in enumerate(candidates[:count])
    ]
    state = SearchState(
        query="Libros sobre realismo mágico",
        language="es",
        filters=SearchFilters(),
        parsed=ParsedQuery(searches=["realismo mágico"], genre="nonfiction"),
        tried=["realismo mágico"],
        candidates=candidates,
        retries=2 if count < 5 else 0,
        picks=picks,
    )
    rules = load_rules()
    cards = []
    for book, pick in zip(candidates, picks):
        links = search_links(book, rules)
        cards.append(
            BookCard(
                **book.model_dump(),
                **pick.model_dump(exclude={"isbn13"}),
                links=links,
                formats=list(dict.fromkeys(f for link in links for f in link.formats)),
            )
        )
    return state, cards
