"""Bounded lazy refresh of stale saved books; optional failures keep the snapshot."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from redis.exceptions import RedisError

from app.repository import StorageUnavailable
from app.sources.edition import lookup_edition

logger = logging.getLogger(__name__)
MAX_AGE = timedelta(days=30)
COOLDOWN_SECONDS = 300
REFRESH_TIMEOUT_SECONDS = 3


class BookRefresh:
    def __init__(
        self,
        repository,
        client,
        redis,
        api_key=None,
        *,
        now=None,
        namespace="lumen:refresh:v1",
    ):
        self.repository = repository
        self.client = client
        self.redis = redis
        self.api_key = api_key
        self.now = now or (lambda: datetime.now(UTC))
        self.namespace = namespace
        self.slots = asyncio.Semaphore(3)

    async def refresh(self, book):
        if self.now() - book.fetched_at < MAX_AGE or self.slots.locked():
            return book
        async with self.slots:
            try:
                # The expiring attempt lease also throttles failed refreshes across
                # workers. It contains no query/IP and never touches usage keys.
                async with asyncio.timeout(REFRESH_TIMEOUT_SECONDS):
                    admitted = await self.redis.set(
                        f"{self.namespace}:{book.isbn13}",
                        "1",
                        nx=True,
                        ex=COOLDOWN_SECONDS,
                    )
                    if not admitted:
                        return book
                    candidate = await lookup_edition(
                        self.client, book.isbn13, book.language, self.api_key
                    )
                    if candidate is not None:
                        updated = await self.repository.refresh_book(book, candidate)
                        if updated is not None:
                            return updated
            except (RedisError, OSError, TimeoutError, StorageUnavailable, ValueError):
                logger.warning("book_refresh_unavailable")
        return book
