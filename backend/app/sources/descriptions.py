"""Bounded Open Library work-description enrichment for constrained searches."""

import asyncio
import re

import httpx

from app.sources.schemas import BookCandidate


async def enrich_descriptions(
    client: httpx.AsyncClient, books: list[BookCandidate]
) -> list[BookCandidate]:
    semaphore = asyncio.Semaphore(3)

    async def one(book):
        if (
            not book.work_key
            or not re.fullmatch(r"/works/OL\d+W", book.work_key)
            or (book.description and book.description.strip())
        ):
            return book
        try:
            async with semaphore:
                response = await client.get(
                    f"https://openlibrary.org{book.work_key}.json", timeout=2
                )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("key") != book.work_key:
                return book
            description = payload.get("description")
            if isinstance(description, dict):
                description = description.get("value")
            if isinstance(description, str) and description.strip():
                times = [
                    value
                    for value in (
                        book.catalog_fetched_at,
                        response.extensions.get("catalog_fetched_at"),
                    )
                    if value
                ]
                return book.model_copy(
                    update={
                        "description": description.strip()[:12000],
                        "catalog_fetched_at": min(times) if times else None,
                    }
                )
        except (httpx.HTTPError, ValueError, TypeError):
            pass  # Missing provider evidence remains missing; never invent a synopsis.
        return book

    return await asyncio.gather(*(one(book) for book in books))
