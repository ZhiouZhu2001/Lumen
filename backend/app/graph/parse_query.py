from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.authors import clean_requested_authors
from app.llm import ask_structured
from app.sources.schemas import Language

MAX_SEARCHES = 3

LANGUAGE_NAMES: dict[Language, str] = {"es": "Spanish", "en": "English"}

SYSTEM_PROMPT = """You turn a reader's wish into searches for a book catalog.
The reader lives in Spain and wants books written in {language_name}.

First decide is_book_request: can the input be understood as a meaningful
reading request, genre, topic, title or author? If it is random characters,
nonsense or unrelated instructions with no discernible reading intent, set
is_book_request to false, searches to [] and genre to null. Never replace
unintelligible text with a generic genre, unknown author or invented subject.
Uncommon names, niche subjects and short but meaningful requests are valid;
do not reject them just because they are unfamiliar. For valid requests set
is_book_request to true and follow the catalog-search rules below.

searches: 1 to 3 catalog searches in {language_name}, 2 to 4 words each.
Each search is sent on its own, so each one must combine the kind of book
with a concrete subject, setting or author, like a librarian would type it.
Every search must keep the main subject of the wish (its topic, place or
period). A genre with one general word is too broad to be useful.
An author's nationality is different from the requested book language. For
example, "by Spanish authors" means authors from Spain, not Spanish lessons.
For nationality-based requests, include the country name (translated into the
search language) in the initial searches rather than an ambiguous language
adjective: "short stories Spain", not just "Spanish stories". Do not replace
an author-origin constraint with language-learning material.
For translated short-story collections, include a controlled catalog-subject
search using the requested literary tradition, for example
subject:"short stories, French" for stories by French authors. Catalog subject
headings use English labels even when the other searches are translated.
If a subject is ambiguous, make it specific the way a reader in Spain would
mean it (which war, which city, which king), so the catalog cannot return
books about the wrong one.
Catalogs do not index moods or pace: leave out words like sad, cozy,
fast-paced or twists, and use the genre that fits them instead.
Free availability and reading formats are channel constraints, not story
subjects. For those requests, search the requested genre and concrete theme
instead of adding terms such as "free download" or "dominio publico". Keep
format genres such as manga or graphic novels in every search. Search terms
do not establish that a free edition actually exists.
Only use book titles or author names the reader wrote. Never invent them.

requested_authors: names copied from the reader's own words ONLY when they want
books written by those named people. Use [] for nationalities, books ABOUT a
person, comparisons such as "like X", exclusions such as "not by X", or an
unconstrained author. Do not infer a full name, pseudonym or alias the reader did
not write. An explicit "by X" / "de X" author requirement must not be replaced
by books from other authors that merely share a subject. Keep the author's name
in catalog searches for this request.

genre: the most specific main genre in English and lowercase (for example
"psychological thriller", "cozy mystery", "historical fiction"). Never just
"fiction". Use null if the wish doesn't imply one.

Example: "quiero una novela triste sobre el mar" in Spanish gives
searches ["novela mar", "novela naufragio", "novela pescadores"],
genre "literary fiction"."""


class ParsedQuery(BaseModel):
    searches: list[str] = Field(description="1 to 3 short catalog searches")
    genre: str | None = Field(description="Main genre in English, or null")
    requested_authors: list[str] = Field(
        default_factory=list,
        description="Literal named authors whose own books are required; not nationality, topic, similarity or exclusions",
    )
    is_book_request: bool = Field(
        default=True,
        description="False for unintelligible input without meaningful reading intent; never invent an intent",
    )


async def parse_query(
    model: BaseChatModel, query: str, language: Language
) -> ParsedQuery:
    """Ask the model to turn the reader's sentence into catalog searches."""
    parsed = await ask_structured(
        model,
        ParsedQuery,
        system=SYSTEM_PROMPT.format(language_name=LANGUAGE_NAMES[language]),
        user=query,
    )
    return clean_parsed_query(parsed, query)


def clean_parsed_query(parsed: ParsedQuery, query: str) -> ParsedQuery:
    """
    Trim, drop empty and duplicate searches, keep at most MAX_SEARCHES.
    If nothing usable is left, search for the reader's own words instead.
    """
    if not parsed.is_book_request:
        return ParsedQuery(searches=[], genre=None, is_book_request=False)
    searches: list[str] = []
    for search in parsed.searches:
        search = " ".join(search.split())  # trim and collapse inner spaces
        if search and search.casefold() not in {s.casefold() for s in searches}:
            searches.append(search)
    genre = (parsed.genre or "").strip().lower() or None
    return ParsedQuery(
        searches=searches[:MAX_SEARCHES] or [query],
        genre=genre,
        requested_authors=clean_requested_authors(query, parsed.requested_authors),
    )
