"""Run the recommendation graph against the configured live services.

From backend/: python -m scripts.try_graph --query "fantasy with dragons" --language en
"""

import argparse
import asyncio
from time import perf_counter

from app.book_cards import BookCardBuilder
from app.config import get_settings
from app.graph.rank import select_for_ranking
from app.graph.search import UpstreamUnavailable
from app.graph.state import SearchState
from app.graph.workflow import build_graph
from app.http_client import make_http_client
from app.llm import LLMError, create_chat_model
from app.sources.schemas import Language


async def main(query: str, language: Language, *, with_channels: bool = False) -> int:
    settings = get_settings()
    model = create_chat_model()
    initial_state = SearchState(
        query=query,
        language=language,
        parsed=None,
        tried=[],
        candidates=[],
        retries=0,
        picks=[],
    )
    started = perf_counter()
    try:
        async with make_http_client() as client:
            graph = build_graph(
                model, client, google_api_key=settings.google_books_api_key
            )
            result = await graph.ainvoke(initial_state)
            channels = (
                await BookCardBuilder(client).build(
                    result["candidates"], result["picks"]
                )
                if with_channels
                else None
            )
    except UpstreamUnavailable:
        print(
            "upstream_unavailable: Book sources are not responding. Please try again."
        )
        return 1
    except LLMError:
        print("llm_failed: The model could not complete the recommendation.")
        return 1

    print("Original query:", result["query"])
    print("Latest parsed query:", result["parsed"])
    print("Broadening retries:", result["retries"])
    print("Searches tried:", result["tried"])
    print("Candidates:", len(result["candidates"]))
    print("Eligible shortlist:", len(select_for_ranking(result["candidates"])))
    print(f"Duration: {perf_counter() - started:.2f}s")
    print("Recommendations:", len(result["picks"]))
    if not result["picks"]:
        print("no_results: No matching books with usable descriptions were found.")
        return 0

    books_by_isbn = {book.isbn13: book for book in result["candidates"]}
    for pick in result["picks"]:
        book = books_by_isbn[pick.isbn13]
        print(f"\n{pick.rank}. {book.title} ({book.isbn13})")
        print(pick.reason)
        if channels:
            card = next(card for card in channels.cards if card.isbn13 == pick.isbn13)
            for link in card.links:
                print(f"  {link.label} ({link.match}): {link.url}")
            print("  Lookup status:", channels.lookups[card.isbn13])
    return 0


def query_argument(value: str) -> str:
    query = value.strip()
    if not 3 <= len(query) <= 300:
        raise argparse.ArgumentTypeError("Query must contain 3 to 300 characters.")
    return query


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--query",
        type=query_argument,
        default="quiero una novela triste sobre el mar",
    )
    parser.add_argument("--language", choices=("en", "es"), default="es")
    parser.add_argument(
        "--with-channels",
        action="store_true",
        help="Attach buying and reading links using real channel APIs",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(main(args.query, args.language, with_channels=args.with_channels))
    )
