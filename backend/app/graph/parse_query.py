from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from app.llm import ask_structured
from app.sources.schemas import Language

MAX_SEARCHES = 3

LANGUAGE_NAMES: dict[Language, str] = {"es": "Spanish", "en": "English"}

SYSTEM_PROMPT = """You turn a reader's wish into searches for a book catalog.
The reader wants books written in {language_name}.

searches: 1 to 3 short catalog searches (1 to 4 words each) in {language_name},
like a librarian would type them: topic, settings, moods, genres.
Only use book titles or author names the reader wrote. Never invent them.

genre: the main genre in English and lowercase (for example "thriller",
"romance","science fiction"), or null if the wish doesn't imply one."""


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
