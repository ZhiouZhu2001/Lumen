"""Manual single-attempt ranking check; use scripts.try_graph for bounded retries."""

import asyncio

from app.config import get_settings
from app.graph.parse_query import parse_query
from app.graph.rank import rank_and_explain
from app.graph.search import search_candidates
from app.http_client import make_http_client
from app.llm import create_chat_model
from app.sources.schemas import Language

QUERY = "una historia de amor durante la Guerra Civil"
LANGUAGE: Language = "es"


async def main() -> None:
    settings = get_settings()
    model = create_chat_model()
    async with make_http_client() as client:
        parsed = await parse_query(model, QUERY, LANGUAGE)
        print(f"searches: {parsed.searches}")
        candidates = await search_candidates(
            client, parsed.searches, LANGUAGE, settings.google_books_api_key
        )
        print(f"candidates: {len(candidates)}\n")
        titles = {book.isbn13: book.title for book in candidates}
        attempt = await rank_and_explain(model, QUERY, LANGUAGE, candidates)
        for pick in attempt.picks:
            print(f"{pick.rank}. {titles[pick.isbn13]} ({pick.isbn13})")
            print(f"   {pick.reason}\n")
        if attempt.feedback:
            print("Validation feedback:")
            for issue in attempt.feedback:
                print(f"- {issue}")


if __name__ == "__main__":
    asyncio.run(main())
