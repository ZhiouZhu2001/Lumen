# Lumen Update Version 9

## 1. Basic Information

- Completion date: 2026-11-08, Europe/Madrid. Initial investigation/branch setup
  began on 2026-11-06; implementation resumed on the same round branch.
- Branch: `codex/update-9-book-channels`.
- Baseline: `a089ab4f036a123b3aca25526a83fa9b70dbd022`, the merged Update 8
  publication record on main. The working tree was clean before this round.
- Objective: attach the specification's buying/reading channels to validated
  recommendations and retain verifiable channel evidence.
- Actual scope: configured search links, Apple Books/Gutendex lookups, work
  matching, book cards, request spacing/cache/failure handling, evaluation/replay,
  terminal integration, packaging, tests and documentation.

The HTTP search endpoint still returns keyword JSON. No frontend, SSE, database
migration, persistence or request-filter implementation was added. The complete
product merge gate remains unsuccessful; this round is local and unuploaded.

## 2. Technologies Used

- Existing Python/Pydantic: validate channel rules, HTTPS links and card data,
  retaining original bibliographic metadata and the validated reason/rank.
- Existing asynchronous httpx: query the already specified iTunes/Gutendex APIs
  using the caller-owned HTTP client. No retailer price scraping was introduced.
- Existing PyYAML: load `app/stores.yaml` with `safe_load`. It was promoted from
  an explicit development dependency to an explicit runtime dependency, so the
  installed application can load rules. No package version changed.
- Standard-library Unicode normalization/regular expressions: compare titles and
  author identity and reject unsafe hosts, mismatched IDs and wrong result types.
- Standard-library asyncio locks, monotonic time and OrderedDict: serialize
  provider queries, space Apple requests, deduplicate completed lookups, bound
  cache size and distinguish outages from valid no-match responses.
- Existing pytest/Ruff/uv tooling: recorded-response tests, fake-clock timing
  tests, runtime-wheel verification and the full offline suite.
- Browser/HTTP inspection: verify retailer search behavior without purchases,
  authentication, access-barrier bypass or collecting prices.

No new framework, model provider, primary bibliographic source, paid service or
recurring subscription was introduced. The recommendation graph and its maximum
two broadenings/six logical model calls remain unchanged.

## 3. Implementation

### Book-card interface and rules

`BookCardBuilder(http_client).build(candidates, picks)` returns `CardBatch` with
ordered cards and separate per-ISBN lookup diagnostics. Picks must be unique,
consecutively ranked and accepted by the existing ISBN/grounding checks before
any channel request occurs. A card never introduces an ISBN from a channel API.

The six configured channels are:

| Channel | Application rule | Link method |
| --- | --- | --- |
| Amazon.es | English/Spanish | ISBN search |
| Apple Books | English/Spanish | Matched ebook in the Spanish storefront |
| Project Gutenberg | English/Spanish | Matched Gutendex text/download evidence |
| Casa del Libro | Spanish | ISBN search |
| Abacus | Spanish | ISBN search |
| Norma Comics | Spanish comics/manga/graphic novels | ISBN search |

Genre recognition includes Spanish labels and word boundaries; "tragicomic"
alone does not establish comic format. Search templates require exactly one
plain `{isbn13}` placeholder and a matching HTTPS host. A new ISBN-search channel
can be added through configuration; verification/tests remain necessary.

Retailer links are search entry points, not stock confirmations. Their format
tags are inferred search options. Generic `ebook` is included for Casa del Libro;
the module does not assert an actual edition exists in every inferred format.

### Verified API links and limits of matching

Apple queries use `country=ES`, `media=ebook`, `entity=ebook` and at most ten
results. A direct link requires matching title/author metadata, ebook kind, the
Spanish Apple Books URL path and the returned track ID. The response does not
verify the ebook's language, so `language_verified` remains false. This is a
work-level link, not proof of the selected ISBN edition.

Gutendex links require matching title/author, requested language, text media,
explicit `copyright: false`, a supported readable/download format and a Gutenberg
URL containing the returned book ID. Known HTTP Gutenberg asset URLs can be
upgraded to HTTPS. The result retains `copyright_region: US`, the source's scope;
it does not certify copyright status in Spain.

Matching normalizes case, accents and punctuation, permits a missing subtitle on
one side, and rejects two different subtitles or explicit numbered-volume
conflicts. Author ordering/additional names are tolerated, while a surname-only
match to a fuller name is rejected. Conservative matching can miss valid editions
and is not a bibliographic authority-ID or exact-edition guarantee.

### Performance, caching and failure behavior

One builder is reused per application process. Apple request starts are at least
3.1 seconds apart. Providers have separate locks and can progress concurrently;
each request has a four-second timeout. Identical completed normalized-work
lookups reuse results across ISBN editions without caching a reader's reason.

The process-local cache is bounded at 512 entries: matches last 15 minutes and
bounded no-match responses one minute. Expected source failures trigger a
30-second provider cooldown, not a fabricated empty catalog. Multiple processes
or replicas still require the planned shared coordination before scaling.

Diagnostics distinguish `matched`, `not_found` (no verified match in the bounded
response), `unavailable`, and `insufficient_metadata`. Optional lookup failure
hides that link and preserves the card/search links. Cancellation propagates and
releases locks. Source failures do not become successful empty-catalog evidence.

Final review found a shared-list issue: mutating an output link's formats could
change configured formats for later cards. Its regression failed before the fix.
Copying the returned format list now isolates output from configuration/cache.

### Integration and evidence

- FastAPI lifespan owns one builder with its existing HTTP client; the keyword
  endpoint's request/response contract is unchanged.
- `scripts.try_graph --with-channels` attaches real links and lookup statuses.
  Without the flag it retains its graph-only behavior.
- The full live evaluator now builds cards after ranking. It records cards,
  lookup statuses, channel errors and separate channel duration, within the
  existing per-case timeout. A channel failure preserves graph evidence.
- Replay uses links only if cards were captured, checks that their ISBNs match
  the picks, and preserves blocked link status for historical captures without
  cards. No graph/channel duration becomes an SSE timing result.
- Source fingerprints include `app/stores.yaml`. Normalized card/source evidence
  and unchanged historical reports remain available for review.

## 4. File Changes

| File | Purpose and before/after behavior |
| --- | --- |
| `backend/app/book_cards.py` | Added; validated picks previously had no channel assembly. The new module builds cards and owns lookup caching, spacing and failure diagnostics. |
| `backend/app/channels/__init__.py` | Added; defines the channel-data package. |
| `backend/app/channels/schemas.py` | Added; typed links/cards/batches distinguish search links, work matches, language evidence and source copyright region. |
| `backend/app/channels/matching.py` | Added; centralizes normalized title/author and safe-host comparisons. |
| `backend/app/channels/rules.py` | Added; validates YAML rules and creates applicable ISBN search links. |
| `backend/app/channels/README.md` | Added; documents the interface, matching limits, performance, sources and actual verification scope. |
| `backend/app/stores.yaml` | Added; contains the six specified language/genre/format/link rules. |
| `backend/app/sources/apple_books.py` | Added; bounded ebook lookup with matched Apple storefront/track links. |
| `backend/app/sources/gutendex.py` | Added; bounded language/rights/text lookup with checked Gutenberg download links. |
| `backend/app/main.py` | Modified; initializes the reusable card builder; previously only HTTP/Redis/database resources were initialized. No endpoint behavior changed. |
| `backend/scripts/try_graph.py` | Modified; adds optional `--with-channels` and prints resulting links/diagnostics. |
| `backend/evals/checks.py` | Modified; Norma checks recognize Spanish genre labels and reject substring false positives. Existing count/free-only/latency requirements remain. |
| `backend/evals/run.py` | Modified; captures real cards and channel timings/errors, uses actual links for checks, and fingerprints the rule file. |
| `backend/evals/replay.py` | Modified; reconstructs captured links when present while preserving legacy missing evidence and blocked SSE checks. |
| `backend/evals/README.md` | Modified; explains the channel-enabled target, captures, timings and remaining filter/SSE gaps. |
| `backend/pyproject.toml` | Modified; moves the already declared YAML parser from development-only to runtime dependencies. |
| `backend/uv.lock` | Modified; synchronizes dependency groups without changing package versions. |
| `backend/tests/test_book_cards.py` | Added; recorded-response card assembly, rules, invalid picks, outages, cache/spacing/cancellation and output isolation. |
| `backend/tests/test_channel_sources.py` | Added; identity, language, rights, URL/ID and configuration edge cases. |
| `backend/tests/test_evals.py` | Modified; adds captured-card replay, channel-failure evidence and bilingual genre checks. |
| `backend/tests/fixtures/apple_channels_live.json` | Added; selected public fields from a real Apple response; prices omitted. |
| `backend/tests/fixtures/gutendex_channels_live.json` | Added; selected public fields from a successful individual-book response; not claimed as a successful search response. |
| `backend/evals/results/eval-20261108T095646341132Z.json` | Added; complete real graph/channel evaluation with all outcomes retained. |
| `backend/evals/results/channel-templates-20261108.json` | Added; actual retailer HTTP/browser observations, including blocked checks. |
| `backend/evals/results/channel-final-verification-20261108.json` | Added; replay/integrity results and explicit source difference after the final defensive-copy fix. |
| `update_version/Lumen_Update_Version_9.md` | Added; this round's actual scope, evidence, remaining work and proposed submission. |

No files were deleted. Existing user work was not overwritten. All new project
explanations are English; Spanish genre labels and original bibliographic data
are intentional localization/source content.

## 5. Project Benefits

Recommendations now have a reusable, tested route to buying/reading options
without allowing channel data to invent books or rewrite selected ISBNs. Failure
status distinguishes missing evidence from a genuine bounded no-match response.
Request spacing, short failure cooldowns and caching reduce avoidable API load.

Recorded cards make link-rule evaluation reproducible instead of permanently
blocked by an absent adapter. Separate provenance makes it possible for a later
UI to distinguish "search this shop" from a matched work and to disclose edition,
language and copyright-evidence limits accurately.

## 6. Verification Actually Performed

### Offline and packaging checks

- Full offline pytest before final isolation review: 210 passed.
- Output-format isolation regression: failed before the defensive-copy fix and
  passed afterward.
- Final full `uv run python -m pytest -q`: **211 passed in 3.63 seconds**, versus
  the 161-test baseline. An earlier final-code run also passed all 211 tests.
- `ruff check app scripts tests evals` from `backend/`: passed.
- Scoped Ruff formatting: passed, 16 Python files; compilation also passed.
- `uv lock --offline`: resolved the existing 71 packages; no version changes.
- `uv build --wheel --offline`: passed, including a final build after the copy fix.
  Archive inspection confirmed the card/rule/source modules and `app/stores.yaml`
  are packaged. No wheel was uploaded or released.
- CLI help shows `--with-channels`; help itself made no API calls.
- `git diff --check`: passed.
- Final language/attribution review passed. New evidence was checked against
  configured API secret values without printing them; no configured secrets were
  present. The final wheel also declares the runtime YAML dependency explicitly.
- Offline replay reproduced all 20 recorded verdicts. Replay/integrity checks
  completed in 0.0437 seconds after imports.

The live capture fingerprints 37 source/rule files. After that capture, only
`app/book_cards.py` changed: a one-line defensive output-list copy. Its regression
and the full 211-test suite verify the final implementation. The capture is not
presented as a second live run of that later fix. The final-verification JSON
records the difference and current fingerprints; all captured verdicts still
replay identically. Further paid model/API calls were not repeated for a change
that affects caller mutation rather than normal lookup results.

Unchanged broad-lint findings documented in prior rounds were not hidden or
repaired; broad repository lint was not rerun. No Docker image rebuild, database
migration or frontend verification was performed because those were outside the
actual change. The wheel check is not described as a deployment test.

### Real API and retailer checks

- Apple returned three matched `Pride and Prejudice` ebook records in its Spanish
  storefront; selected bibliographic/link fields were saved as a fixture.
- Gutendex individual book 1342 responded successfully. Its search endpoint timed
  out in initial probes and throughout the full channel run. Both documented
  slash/no-slash search forms were checked afterward and timed out; the missing
  links are not attributed to a proven canonical-URL redirect problem.
- Casa del Libro: the configured URL opened a prefilled ISBN modal. Clicking
  **Buscar** displayed one matching Don Quijote result. No cart action occurred.
- Abacus: HTTP 200 and an ISBN-specific search-page title were observed.
- Amazon.es and Norma Comics: earlier 2026-11-06 probes returned ISBN result
  pages, but current automated checks returned 503/403. Current rendering remains
  unverified; no CAPTCHA or access barrier was bypassed.

A local report writer initially failed because the Python environment lacked
timezone data. The successful HTTP observations were preserved into the template
report using UTC metadata without repeating requests or installing another
dependency. This incidental writer failure is not a successful website check.

### Complete live graph/channel run

`python -u -X utf8 -m evals.run --live` used the existing configured
`openai:gpt-5.4-mini` model and actual catalog/channel clients. It ran from
**2026-11-08 10:56:56 to 11:04:08 Europe/Madrid**.

- Cases: **20/20 complete**, zero workflow or channel-assembly exceptions.
- Cards: **126**, each matching its captured recommendation ISBN.
- Logical model calls: **48**, at most six per query; no graph budget changes.
- Captured lookup statuses, including cache/cooldown results:
  Apple: 66 matched, 58 no verified match, two insufficient metadata.
  Gutenberg: 124 unavailable, two insufficient metadata. These are lookup
  outcomes, not counts of actual network requests.
- Links: 126 Amazon searches, 66 matched Apple links, 59 Casa del Libro searches,
  59 Abacus searches and two Norma Comics searches. No live Gutenberg search
  match was established.
- Graph durations: about 0.62–10.02 seconds. Channel attachment added up to
  **28.38 seconds** per batch, including request-spacing waits. Total test time
  and neither duration establish first-book HTTP SSE latency.

| Check | Actual result |
| --- | --- |
| Authenticity | 20 pass |
| Book language | 20 pass |
| Count | 20 pass |
| Reason heuristic | 20 pass |
| Channel rules | 18 pass, two fail |
| First-book SSE latency | 18 blocked, two nonsense cases not applicable |

The failed channel cases are `en_free_classics` and `es_free_classics`. Their
10/8 selected books lacked verified Gutenberg links because lookup was unavailable.
Ordinary ISBN store searches cannot satisfy free-only evidence. Both empty
nonsense cases have no cards and pass the vacuous link rule; they are not
positive channel examples. Filters remain explicitly unsupported in eight cases.

The live command and offline replay correctly exit 1. The full six-check merge
gate has **not passed**. Recorded-response tests are not substituted for a
successful real Gutendex search, current retailer rendering or HTTP SSE test.

## 7. Future Impact and Remaining Work

The public keyword-search contract, frontend, graph routing, model-call limit,
database schema and deployment configuration are unchanged. Runtime YAML support
is now explicit. The local memory cache/limiter needs shared coordination for
multiple processes; it is not the planned Redis/IP/daily-AI-cap implementation.

This batch card interface can take longer than 15 seconds to finish. Future SSE
integration needs incremental delivery and a real HTTP timing measurement rather
than waiting for every optional channel or reusing graph-only timings.

Resolve free-source search availability, implement verified free-only and other
filters, and connect cards to the HTTP/frontend stream before claiming complete
product evaluation. Edition identity, Apple book language and Spain copyright
eligibility require stronger evidence than the current work-level source match.
Search-entry links still do not guarantee stock or formats. The current webpage
does not yet display these new card links; the terminal/evaluator can exercise them.

No new major decision outside the existing specification was implemented. There
was no provider replacement, irreversible migration, release or deployment.
Returning to main's baseline reverses this round without a data migration.

## 8. Approvals and GitHub Submission

The user instructed continuing the next step. Channels and their two API sources
were already specified; the work stays within that scope and the existing stack.
The prior staged main merge was specific to Update 8 and is not treated as an
automatic exception for this round.

Update 9 is local, uncommitted and unpushed. Upload confirmation is pending;
main has not been modified by this implementation. No pull request, collaborator,
author credit, release or deployment was created.

### Proposed commit title

`feat: attach buying and reading channels to validated book cards`

### Proposed description

Add six configured channel rules and a reusable book-card module with ISBN
membership/grounding validation, conservative title/author matching, checked
Apple/Gutenberg URLs and explicit lookup provenance. Distinguish ISBN store
searches from matched works, source rights/language limits and unavailable APIs.
Bound request spacing, caching and failure cooldowns, and isolate output data
from configuration. Initialize the module with the application HTTP client and
expose optional terminal integration plus captured-card evaluation/replay.

Validation: 211 offline tests, scoped lint/formatting and wheel packaging checks
pass. The 20-case live run passes authenticity/language/count/reason checks;
channel checks pass 18 and fail the two free-only cases because Gutendex search
is unavailable. HTTP SSE remains unmeasured and filters unsupported, so the full
gate correctly remains unsuccessful. Retain real fixtures, retailer observations,
the full report and the explicitly documented post-capture defensive-copy fix.

Compatibility: no public API, frontend, database or graph-budget change. Promote
the existing YAML parser to a declared runtime dependency without changing its
version. Shared Redis coordination, verified filtering, robust free-source lookup
and incremental HTTP delivery remain future work. See
`update_version/Lumen_Update_Version_9.md` for actual evidence, source limits and
pending upload confirmation.
