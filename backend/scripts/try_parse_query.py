"""Manual check of parse_query. Run: uv run python scripts/try_parse_query.py"""

import asyncio

from app.graph.parse_query import parse_query
from app.llm import create_chat_model
from app.sources.schemas import Language

EXAMPLES: list[tuple[str, Language]] = [
    ("quiero una novela triste sobre el mar", "es"),
    ("fast-paced Spanish thriller with twists", "es"),
    ("something cozy like Agatha Christie", "en"),
]


async def main() -> None:
    model = create_chat_model()
    for query, language in EXAMPLES:
        parsed = await parse_query(model, query, language)
        print(f"{language} | {query}\n  -> {parsed}\n")


asyncio.run(main())
