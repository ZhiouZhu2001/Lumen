"""Manual check that the model call works. Run: uv run python scripts/try_llm.py"""

import asyncio

from pydantic import BaseModel, Field

from app.diagnostics import diagnostic_model
from app.llm import ask_structured


class BookWish(BaseModel):
    genre: str = Field(description="Main literary genre")
    keywords: list[str] = Field(description="3 to 5 short search keywords")


async def main() -> None:
    async with diagnostic_model() as model:
        wish = await ask_structured(
            model,
            BookWish,
            system="You turn a reader's wish into search terms for a book catalog.",
            user="quiero una novela triste sobre el mar",
        )
        print(wish)


if __name__ == "__main__":
    asyncio.run(main())
