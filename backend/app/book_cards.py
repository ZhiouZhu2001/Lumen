"""Build book cards from validated picks, with bounded optional channel lookups."""

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from time import monotonic

import httpx

from app.channels.matching import author_tokens, normalize, safe_url, title_key
from app.channels.rules import StoreRule, applies, load_rules, search_links
from app.channels.schemas import BookLink, CardBatch, LookupStatus
from app.graph.rank import ModelPick, ModelPicks, Pick, validate_picks
from app.sources.apple_books import lookup_apple_books
from app.sources.schemas import BookCandidate

APPLE_INTERVAL = 3.1  # At most 20 request starts in a rolling minute per instance.
CACHE_LIMIT = 512


class BookCardBuilder:
    """Reuse one instance per application process; the caller owns its HTTP client.

    Matching is work-level, not ISBN-edition verification. Retailer links search
    by ISBN and do not establish stock or actual format availability. API failures
    hide only the affected optional link and remain visible in lookup diagnostics.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        rules: list[StoreRule] | None = None,
        clock: Callable[[], float] = monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._client = client
        self._rules = load_rules() if rules is None else rules
        self._clock = clock
        self._sleep = sleep
        if any(r.provider not in (None, "apple_books") for r in self._rules):
            raise ValueError("Only Apple Books lookups are currently supported")
        self._locks = {"apple_books": asyncio.Lock()}
        self._next_apple = 0.0
        self._unavailable_until: dict[str, float] = {}
        self._cache: OrderedDict[tuple, tuple[float, BookLink | None]] = OrderedDict()

    async def _lookup(
        self, rule: StoreRule, book: BookCandidate
    ) -> tuple[BookLink | None, LookupStatus]:
        authors = [author for author in book.authors if author_tokens(author)]
        if not title_key(book.title) or not authors:
            return None, "insufficient_metadata"
        book = book.model_copy(update={"authors": authors})
        provider = rule.provider
        key = (
            provider,
            normalize(book.title),
            tuple(sorted(normalize(a) for a in authors)),
            book.language,
        )
        async with self._locks[provider]:
            cached = self._cache.get(key)
            if cached and cached[0] > self._clock():
                self._cache.move_to_end(key)
                link = cached[1]
                return (
                    link.model_copy(deep=True) if link else None
                ), "matched" if link else "not_found"
            if self._unavailable_until.get(provider, 0) > self._clock():
                return None, "unavailable"
            if provider == "apple_books":
                delay = self._next_apple - self._clock()
                if delay > 0:
                    await self._sleep(delay)
                self._next_apple = self._clock() + APPLE_INTERVAL
            try:
                link = await lookup_apple_books(self._client, book)
                if link and not safe_url(link.url, rule.host):
                    raise ValueError("Lookup URL does not match the configured store")
            except (httpx.HTTPError, ValueError, TypeError):
                # Never cache an outage as an authoritative empty catalog result.
                self._unavailable_until[provider] = self._clock() + 30
                return None, "unavailable"
            self._cache[key] = (self._clock() + (900 if link else 60), link)
            self._cache.move_to_end(key)
            while len(self._cache) > CACHE_LIMIT:
                self._cache.popitem(last=False)
            return (
                link.model_copy(deep=True) if link else None
            ), "matched" if link else "not_found"

    async def build(
        self,
        candidates: list[BookCandidate],
        picks: list[Pick],
        *,
        lookup_timeout: float | None = None,
    ) -> CardBatch:
        """Return cards in pick order; invalid picks fail before any HTTP request."""
        books = {book.isbn13: book for book in candidates}
        proposed = ModelPicks(
            picks=[ModelPick(isbn13=p.isbn13, reason=p.reason) for p in picks]
        )
        valid, _ = validate_picks(proposed, candidates)
        if (
            len(books) != len(candidates)
            or len(picks) != len(valid)
            or [p.isbn13 for p in picks] != [p.isbn13 for p in valid]
            or [p.rank for p in picks] != list(range(1, len(picks) + 1))
        ):
            raise ValueError("Book cards require unique validated picks in rank order")

        async def optional_lookup(rule, book):
            if lookup_timeout is None:
                return await self._lookup(rule, book)
            if lookup_timeout <= 0:
                return None, "unavailable"
            try:
                async with asyncio.timeout(lookup_timeout):
                    return await self._lookup(rule, book)
            except TimeoutError:
                # A timeout is missing optional evidence, never a no-match.
                return None, "unavailable"

        async def one(pick: Pick):
            book = books[pick.isbn13]
            links = search_links(book, self._rules)
            lookup_rules = [
                rule
                for rule in self._rules
                if rule.mode == "lookup" and applies(rule, book)
            ]
            outcomes = await asyncio.gather(
                *(optional_lookup(rule, book) for rule in lookup_rules)
            )
            statuses = {}
            for rule, (link, status) in zip(lookup_rules, outcomes, strict=True):
                statuses[rule.id] = status
                if link:
                    links.append(
                        link.model_copy(
                            update={
                                "store": rule.id,
                                "label": rule.label,
                                "formats": list(rule.formats),
                            }
                        )
                    )
            return {
                **book.model_dump(),
                "rank": pick.rank,
                "reason": pick.reason,
                "links": links,
                "formats": list(
                    dict.fromkeys(f for link in links for f in link.formats)
                ),
            }, statuses

        results = await asyncio.gather(*(one(pick) for pick in picks))
        return CardBatch(
            cards=[card for card, _ in results],
            lookups={
                pick.isbn13: statuses
                for pick, (_, statuses) in zip(picks, results, strict=True)
            },
        )
