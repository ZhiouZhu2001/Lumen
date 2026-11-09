"""Manual check of parse_query. Run: uv run python scripts/try_parse_query.py"""

import asyncio

from app.diagnostics import diagnostic_model
from app.graph.parse_query import parse_query
from app.sources.schemas import Language

EXAMPLES: list[tuple[str, Language]] = [
    ("una historia de amor durante la Guerra Civil", "es"),
    ("fast-paced Spanish thriller with twists", "es"),
    ("something cozy like Agatha Christie", "en"),
]


async def main() -> None:
    async with diagnostic_model() as model:
        for query, language in EXAMPLES:
            parsed = await parse_query(model, query, language)
            print(f"{language} | {query}\n  -> {parsed}\n")


if __name__ == "__main__":
    asyncio.run(main())
