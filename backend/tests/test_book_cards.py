import asyncio
import json
from copy import deepcopy
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from app.book_cards import APPLE_INTERVAL, BookCardBuilder
from app.channels.rules import StoreRule, load_rules
from app.graph.rank import Pick
from app.sources.isbn import isbn13_check_digit
from app.sources.schemas import BookCandidate

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / f"{name}_channels_live.json").read_text("utf-8"))


def book(n=0, **changes):
    prefix = f"97884{n:07d}"
    return BookCandidate(
        **{
            "isbn13": prefix + isbn13_check_digit(prefix),
            "title": "Pride and Prejudice",
            "authors": ["Jane Austen"],
            "language": "en",
            "description": "A novel about relationships.",
            "source": "google_books",
            **changes,
        }
    )


def pick(b, rank=1, reason="A novel about relationships. It fits."):
    return Pick(isbn13=b.isbn13, rank=rank, reason=reason)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, delay):
        self.now += delay
        await asyncio.sleep(0)


def recorded(request):
    if request.url.host == "itunes.apple.com":
        assert request.url.params["country"] == "ES"
        assert request.url.params["entity"] == "ebook"
        return httpx.Response(200, json=fixture("apple"))
    assert request.url.host == "gutendex.com"
    assert request.url.params["languages"] == "en"
    assert request.url.params["copyright"] == "false"
    return httpx.Response(200, json=fixture("gutendex"))


async def test_cards_use_recorded_matched_channels_and_preserve_bibliographic_data():
    b = book()
    async with httpx.AsyncClient(transport=httpx.MockTransport(recorded)) as client:
        batch = await BookCardBuilder(client).build([b], [pick(b)])
    card = batch.cards[0]
    assert card.isbn13 == b.isbn13
    assert card.description == b.description
    assert {link.store for link in card.links} == {
        "amazon_es",
        "apple_books",
        "gutenberg",
    }
    assert batch.lookups[b.isbn13] == {"apple_books": "matched", "gutenberg": "matched"}
    free = next(link for link in card.links if link.store == "gutenberg")
    assert free.copyright_region == "US"
    assert free.language_verified is True
    apple = next(link for link in card.links if link.store == "apple_books")
    assert apple.language_verified is False
    assert all(link.match == "title_author" for link in (free, apple))
    assert card.formats == ["paper", "kindle", "apple_books", "free"]


@pytest.mark.parametrize(
    ("language", "genres", "stores"),
    [
        ("en", ["Manga"], {"amazon_es"}),
        ("es", ["Fiction"], {"amazon_es", "casa_del_libro", "abacus"}),
        (
            "es",
            ["Comics & Graphic Novels"],
            {"amazon_es", "casa_del_libro", "abacus", "norma_comics"},
        ),
        (
            "es",
            ["Novela gráfica"],
            {"amazon_es", "casa_del_libro", "abacus", "norma_comics"},
        ),
        ("es", ["Tragicomic fiction"], {"amazon_es", "casa_del_libro", "abacus"}),
    ],
)
async def test_store_language_and_genre_rules(language, genres, stores):
    b = book(language=language, genres=genres)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"results": []})
        )
    ) as client:
        result = await BookCardBuilder(client).build([b], [pick(b)])
    assert {link.store for link in result.cards[0].links} == stores
    assert all(b.isbn13 in link.url for link in result.cards[0].links)


@pytest.mark.parametrize(
    "defect", ["unknown", "duplicate", "rank", "unsupported_reason", "bad_checksum"]
)
async def test_invalid_picks_fail_before_contacting_any_channel(defect):
    b = book()
    p = pick(b)
    selected = [p]
    if defect == "unknown":
        selected = [pick(book(1))]
    elif defect == "duplicate":
        selected = [p, p]
    elif defect == "rank":
        p.rank = 3
    elif defect == "unsupported_reason":
        p.reason = "A trip to Atlantis."
    else:
        b.isbn13 = b.isbn13[:-1] + str((int(b.isbn13[-1]) + 1) % 10)
        p.isbn13 = b.isbn13
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: pytest.fail("Unexpected network request")
        )
    ) as client:
        with pytest.raises(ValueError, match="validated picks"):
            await BookCardBuilder(client).build([b], selected)


async def test_missing_author_metadata_and_empty_results_do_not_make_api_calls():
    b = book(authors=[])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: pytest.fail("Unexpected network request")
        )
    ) as client:
        builder = BookCardBuilder(client)
        assert (await builder.build([], [])).cards == []
        result = await builder.build([b], [pick(b)])
    assert {link.store for link in result.cards[0].links} == {"amazon_es"}
    assert set(result.lookups[b.isbn13].values()) == {"insufficient_metadata"}


@pytest.mark.parametrize("failure", ["status", "timeout", "json", "schema"])
async def test_optional_channel_failure_is_distinct_from_no_match_and_keeps_cards(
    failure,
):
    def handler(request):
        if request.url.host == "itunes.apple.com":
            return httpx.Response(200, json=fixture("apple"))
        if failure == "timeout":
            raise httpx.ReadTimeout("Simulated outage", request=request)
        if failure == "status":
            return httpx.Response(503)
        if failure == "json":
            return httpx.Response(200, text="not json")
        return httpx.Response(200, json={"results": None})

    b = book()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        batch = await BookCardBuilder(client).build([b], [pick(b)])
    assert {link.store for link in batch.cards[0].links} == {"amazon_es", "apple_books"}
    assert batch.lookups[b.isbn13]["gutenberg"] == "unavailable"


async def test_cache_deduplicates_work_lookups_and_does_not_cache_reader_reasons():
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return recorded(request)

    b, edition = book(), book(1)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        builder = BookCardBuilder(client)
        first = await builder.build([b, edition], [pick(b), pick(edition, 2)])
        first.cards[0].links[1].url = "https://example.test/changed"
        second = await builder.build(
            [b], [pick(b, reason="A relationship novel. It fits.")]
        )
    assert calls.count("itunes.apple.com") == calls.count("gutendex.com") == 1
    assert second.cards[0].reason == "A relationship novel. It fits."
    assert all("example.test" not in link.url for link in second.cards[0].links)


async def test_rate_gate_spaces_distinct_apple_requests_without_real_waits():
    clock, starts = Clock(), []

    def handler(request):
        starts.append(clock())
        return httpx.Response(200, json={"results": []})

    rules = [rule for rule in load_rules() if rule.id == "apple_books"]
    books = [book(n, title=f"Different title {n}") for n in range(4)]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await BookCardBuilder(
            client, rules=rules, clock=clock, sleep=clock.sleep
        ).build(books, [pick(b, n + 1) for n, b in enumerate(books)])
    assert len(starts) == 4
    assert all(b - a >= APPLE_INTERVAL - 1e-9 for a, b in pairwise(starts))


async def test_failure_cooldown_expires_and_does_not_become_cached_absence():
    clock, calls = Clock(), []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(503)
            if len(calls) == 1
            else httpx.Response(200, json=fixture("gutendex"))
        )

    rules = [rule for rule in load_rules() if rule.id == "gutenberg"]
    b = book()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        builder = BookCardBuilder(client, rules=rules, clock=clock, sleep=clock.sleep)
        for _ in range(2):
            result = await builder.build([b], [pick(b)])
            assert result.lookups[b.isbn13]["gutenberg"] == "unavailable"
        assert len(calls) == 1
        clock.now = 31
        recovered = await builder.build([b], [pick(b)])
    assert recovered.lookups[b.isbn13]["gutenberg"] == "matched"
    assert len(calls) == 2


def test_search_store_can_be_added_by_configuration():
    original = next(rule for rule in load_rules() if rule.id == "amazon_es")
    data = deepcopy(original.model_dump())
    data.update(
        id="another_shop",
        label="Another shop",
        host="example.test",
        url_template="https://example.test/?isbn={isbn13}",
    )
    assert StoreRule.model_validate(data).id == "another_shop"


async def test_negative_cache_expires_without_becoming_permanent_absence():
    clock, calls = Clock(), []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"results": []} if len(calls) == 1 else fixture("apple")
        )

    rules = [rule for rule in load_rules() if rule.id == "apple_books"]
    b = book()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        builder = BookCardBuilder(client, rules=rules, clock=clock, sleep=clock.sleep)
        for _ in range(2):
            assert (await builder.build([b], [pick(b)])).lookups[b.isbn13][
                "apple_books"
            ] == "not_found"
        assert len(calls) == 1
        clock.now = 61
        assert (await builder.build([b], [pick(b)])).lookups[b.isbn13][
            "apple_books"
        ] == "matched"
    assert len(calls) == 2


async def test_cancelling_a_lookup_releases_its_lock_for_later_requests():
    clock, entered = Clock(), asyncio.Event()
    count = 0

    async def handler(request):
        nonlocal count
        count += 1
        if count == 1:
            entered.set()
            await asyncio.Future()
        return httpx.Response(200, json=fixture("apple"))

    rules = [rule for rule in load_rules() if rule.id == "apple_books"]
    b = book()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        builder = BookCardBuilder(client, rules=rules, clock=clock, sleep=clock.sleep)
        task = asyncio.create_task(builder.build([b], [pick(b)]))
        await asyncio.wait_for(entered.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        result = await asyncio.wait_for(builder.build([b], [pick(b)]), timeout=1)
    assert result.lookups[b.isbn13]["apple_books"] == "matched"


async def test_mutating_returned_link_formats_does_not_change_configured_rules():
    rules = [rule for rule in load_rules() if rule.id == "apple_books"]
    b = book()
    async with httpx.AsyncClient(transport=httpx.MockTransport(recorded)) as client:
        builder = BookCardBuilder(client, rules=rules)
        first = await builder.build([b], [pick(b)])
        first.cards[0].links[0].formats.append("free")
        second = await builder.build([b], [pick(b)])
    assert second.cards[0].formats == ["apple_books"]
    assert rules[0].formats == ["apple_books"]
