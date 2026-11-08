"""Versioned private search snapshots and validated, public result replay."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.channels.matching import safe_url
from app.channels.rules import applies, load_rules, search_links
from app.channels.schemas import BookCard
from app.filters import SearchFilters
from app.graph.state import SearchState


def signature(model: str) -> str:
    root = Path(__file__).parent
    digest = hashlib.sha256(model.encode())
    for path in sorted([*root.rglob("*.py"), root / "stores.yaml"]):
        digest.update(path.relative_to(root).as_posix().encode())
        # Git line-ending conversion must not change cache semantics.
        digest.update(path.read_text("utf-8").replace("\r\n", "\n").encode())
    return digest.hexdigest()[:24]


def cache_key(namespace: str, payload) -> str:
    body = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return namespace + ":" + hashlib.sha256(body.encode()).hexdigest()


class CompletedSearch(BaseModel):
    state: SearchState
    cards: list[BookCard] = Field(max_length=10)


class SearchCache:
    def __init__(self, cache, model: str):
        self.cache = cache
        self.version = signature(model)
        self.rules = load_rules()

    def key(self, kind: str, payload) -> str:
        return cache_key(f"lumen:cache:v1:{self.version}:{kind}", payload)

    def result_key(self, query, language, filters: SearchFilters):
        return self.key("result", [query, language, filters.model_dump(mode="json")])

    async def get_completed(self, query, language, filters, repository):
        key = self.result_key(query, language, filters)
        value = await self.cache.get(key)
        if value is None:
            return None
        try:
            result = CompletedSearch.model_validate(value)
            state = result.state
            if (
                state["query"] != query
                or state["language"] != language
                or state.get("filters", SearchFilters()) != filters
            ):
                raise ValueError("Cached request mismatch")
            repository.validate_completed(state, result.cards, 0)
            for card in result.cards:
                expected = search_links(card, self.rules)
                static = [link for link in card.links if link.match == "isbn_search"]
                if static != expected or len(
                    {link.store for link in card.links}
                ) != len(card.links):
                    raise ValueError("Cached channel rules changed")
                for link in card.links:
                    rule = next((r for r in self.rules if r.id == link.store), None)
                    if (
                        rule is None
                        or not applies(rule, card)
                        or not safe_url(link.url, rule.host)
                        or link.label != rule.label
                        or link.formats != rule.formats
                        or link.language_verified
                        or link.copyright_region is not None
                        or (
                            link.match == "title_author"
                            and rule.provider != "apple_books"
                        )
                    ):
                        raise ValueError("Invalid cached channel")
                if card.formats != list(
                    dict.fromkeys(f for link in card.links for f in link.formats)
                ):
                    raise ValueError("Cached format mismatch")
            return result
        except (ValueError, TypeError, KeyError):
            await self.cache.delete(key)
            return None

    async def put_completed(self, state, cards):
        # Candidate public serialization excludes internal catalog identifiers.
        # Those identifiers are not needed for completed-result replay.
        value = CompletedSearch(state=state, cards=cards).model_dump(mode="json")
        await self.cache.put(
            self.result_key(
                state["query"], state["language"], state.get("filters", SearchFilters())
            ),
            value,
            6 * 3600,
        )
