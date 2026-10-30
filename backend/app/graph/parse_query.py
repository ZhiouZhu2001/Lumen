from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.llm import ask_structured
from app.sources.schemas import Language

MAX_SEARCHES = 3

LANGUAGE_NAMES: dict[Language, str] = {"es": "Spanish", "en": "English"}

SYSTEM_PROMPT = """You turn a reader's wish into searches for a book catalog.
The reader lives in Spain and wants books written in {language_name}.

searches: 1 to 3 catalog searches in {language_name}, 2 to 4 words each.
Each search is sent on its own, so each one must combine the kind of book
with a concrete subject, setting or author, like a librarian would type it.
Every search must keep the main subject of the wish (its topic, place or
period). A genre with one general word is too broad to be useful.
If a subject is ambiguous, make it specific the way a reader in Spain would
mean it (which war, which city, which king), so the catalog cannot return
books about the wrong one.
Catalogs do not index moods or pace: leave out words like sad, cozy,
fast-paced or twists, and use the genre that fits them instead.
Only use book titles or author names the reader wrote. Never invent them.

genre: the most specific main genre in English and lowercase (for example
"psychological thriller", "cozy mystery", "historical fiction"). Never just
"fiction". Use null if the wish doesn't imply one.

Example: "quiero una novela triste sobre el mar" in Spanish gives
searches ["novela mar", "novela naufragio", "novela pescadores"],
genre "literary fiction"."""


class ParsedQuery(BaseModel):
    searches: list[str] = Field(description="1 to 3 short catalog searches")
    genre: str | None = Field(description="Main genre in English, or null")


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
    searches: list[str] = []
    for search in parsed.searches:
        search = " ".join(search.split())  # trim and collapse inner spaces
        if search and search.casefold() not in {s.casefold() for s in searches}:
            searches.append(search)
    genre = (parsed.genre or "").strip().lower() or None
    return ParsedQuery(searches=searches[:MAX_SEARCHES] or [query], genre=genre)
