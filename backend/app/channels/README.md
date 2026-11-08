# Book-card channel module

`BookCardBuilder(http_client).build(candidates, picks)` attaches buying/reading
links to validated recommendations. Reuse one builder per application process;
the caller owns the HTTP client. The FastAPI lifespan initializes
`app.state.book_cards`, and the live evaluator shares one instance across cases.
The keyword JSON search endpoint has not yet been switched to graph/card output.

For a single terminal search from `backend/`:

```console
uv run python -m scripts.try_graph --language en --query "Classic romantic novels by Jane Austen" --with-channels
```

Without `--with-channels`, the terminal runner retains its previous graph-only
behavior. The card module does not add model calls, change graph routing, write
database rows or fetch retailer prices.

## Rules and matching

`app/stores.yaml` contains the six specified channels and their language, genre,
format and link methods. A new ISBN search channel can be configured with one
entry; its URL template and expectations still need verification/tests.

Amazon.es supports both book languages. Casa del Libro and Abacus are Spanish-only
under the project rules. Norma Comics additionally requires comic/manga/graphic
novel metadata, including Spanish genre labels. A substring such as "tragicomic"
does not establish comic format. Search templates accept exactly one plain
`{isbn13}` placeholder and must match their configured HTTPS host.

Search links are ISBN search entry points, **not stock confirmations**. Their
format tags are inferred search options from the rule. They do not prove that
the selected edition exists in each listed format.

Apple Books is searched through the iTunes API with `country=ES`, `media=ebook`
and `entity=ebook`. Returned links must be HTTPS Apple Books URLs for the Spanish
storefront and must contain the returned track ID. Normalized title and author
identity must match. This is a work-level match, not proof of the exact ISBN
edition. The API response does not establish the ebook's language; the link
retains `language_verified: false` so a future UI can ask readers to check the
edition rather than asserting an unverified language.

Gutendex requires a matching title/author, the requested language, text media,
an explicit `copyright: false`, and a supported download URL on a Gutenberg host
whose path matches the returned book ID. The link retains
`copyright_region: US`: this is the API's reported scope, not verification of
rights in Spain. Missing, unknown or incompatible evidence hides that optional
link. It never creates a new recommendation or a replacement ISBN.

Title matching normalizes case, accents and punctuation. A subtitle may be absent
on one record; two differing subtitles or numbered volumes are not merged.
Author matching tolerates ordering and additional names but rejects a surname-only
match to a fuller name. These conservative rules can miss valid editions; they
are not bibliographic authority identifiers or guarantees of edition identity.

## Failure and performance behavior

The result has `cards` and separate per-ISBN `lookups` diagnostics. Statuses are:

- `matched`: a usable supported link was validated against the response.
- `not_found`: no verified match in the bounded response, not proof of absence
  from the entire catalog. Apple returns at most 10 records; Gutendex uses one page.
- `unavailable`: HTTP error, timeout, malformed response, or the provider's short
  failure cooldown. This is never cached as a genuine empty catalog.
- `insufficient_metadata`: no usable title/author evidence for a lookup.

Requests time out after four seconds. Each provider serializes its requests;
separate providers may run concurrently. Apple request starts are at least 3.1
seconds apart, respecting its documented approximate 20/minute limit per builder.
The 512-entry memory cache retains positive matches for 15 minutes and bounded
no-match results for one minute. Failures trigger a 30-second provider cooldown.
Concurrent identical work lookups share the completed cached result.

This limiter/cache is process-local. Multiple workers or replicas require the
planned shared Redis coordination before scaling. A ten-book batch can wait for
several spaced Apple calls; this batch interface does not establish first-book
SSE latency. Caller cancellation propagates and releases lookup locks.

Picks must be unique, ranked consecutively and pass the existing grounding and
ISBN checks before any channel request starts. Book metadata/reasons stay on the
card; reader-specific reasons and original reader queries are not cached or sent
to channel APIs. The cache contains only public work metadata and lookup results.

## Sources and verification

- [Gutendex documentation](https://gutendex.com/) defines language/copyright filters
  and download metadata, including the USA scope of its copyright field.
- [Apple's Search API documentation](https://performance-partners.apple.com/search-api)
  defines the ebook/storefront query and approximate request limit.
- `evals/results/channel-templates-20261108.json` records actual retailer checks.
  Casa del Libro's query URL opens a prefilled modal; clicking **Buscar** showed
  the matching ISBN result. Abacus returned an ISBN-specific result-page title.
  Current automated Amazon/Norma checks were blocked; earlier successful search
  pages do not prove current uptime. No access barrier was bypassed.

Recorded Apple and Gutendex individual-book response fields are in
`tests/fixtures/*_channels_live.json`. They contain public bibliographic/link data,
not prices. The Gutendex search endpoint timed out during the initial live probe;
individual-book success is not claimed as successful production search matching.
