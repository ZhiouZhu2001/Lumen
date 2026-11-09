"""Manual check of broaden. Run: uv run python scripts/try_broaden.py"""

import asyncio

from app.diagnostics import diagnostic_model
from app.graph.broaden import broaden
from app.graph.parse_query import parse_query
from app.sources.schemas import Language

QUERY = "una historia de amor durante la Guerra Civil"
LANGUAGE: Language = "es"


async def main() -> None:
    async with diagnostic_model() as model:
        tried = (await parse_query(model, QUERY, LANGUAGE)).searches
        print(f"first try: {tried}")
        for retry in (1, 2):  # spec: at most 2 retries
            wider = await broaden(model, QUERY, LANGUAGE, tried)
            print(f"retry {retry}: {wider.searches}")
            tried += wider.searches


if __name__ == "__main__":
    asyncio.run(main())
