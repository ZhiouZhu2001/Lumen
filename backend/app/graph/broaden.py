from langchain_core.language_models import BaseChatModel

from app.graph.parse_query import LANGUAGE_NAMES, ParsedQuery, clean_parsed_query
from app.llm import ask_structured
from app.sources.schemas import Language

SYSTEM_PROMPT = """You help a book search that found too few books.
The reader lives in Spain and wants books written in {language_name}.
You get the reader's wish and the catalog searches that were already tried.

searches: 1 to 3 new, wider catalog searches in {language_name}, 2 to 4 words
each. Keep the main subject of the wish, but drop details, use a broader genre
or a closely related subject. Never repeat a search that was already tried.
Only use book titles or author names the reader wrote. Never invent them.

genre: the most specific main genre in English and lowercase, or null."""


async def broaden(
    model: BaseChatModel, query: str, language: Language, tried: list[str]
) -> ParsedQuery:
    """Ask the model for wider searches than the ones already tried."""
    tried_list = "\n".join(f"- {search}" for search in tried)
    parsed = await ask_structured(
        model,
        ParsedQuery,
        system=SYSTEM_PROMPT.format(language_name=LANGUAGE_NAMES[language]),
        user=f"Reader's wish: {query}\n\nSearches already tried:\n{tried_list}",
    )
    return drop_tried_searches(clean_parsed_query(parsed, query), tried)


def drop_tried_searches(parsed: ParsedQuery, tried: list[str]) -> ParsedQuery:
    """Remove searches we already ran. An empty list means: nothing new to try."""
    seen = {search.casefold() for search in tried}
    new = [search for search in parsed.searches if search.casefold() not in seen]
    return ParsedQuery(searches=new, genre=parsed.genre)
