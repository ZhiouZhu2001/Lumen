# Catalog coverage and original provider objects

Completed recommendation searches cache every merged candidate with a canonical
ISBN-13, supported matching language and nonblank title. Candidates excluded from
ranking or not selected by the model still belong in `books`. Only validated
selected cards become `search_results`. Books, the anonymous search and its
recommendations commit together; a failure, duplicate search ID, conflicting ISBN
language or cancellation rolls the transaction back. ISBN locks are acquired in
sorted order. A completed no-picks search can cache real candidates; an empty
candidate set creates no book rows. The legacy keyword JSON endpoint is read-only.

## Evidence format and boundaries

The existing JSONB `books.raw` envelope keeps `snapshot_version: 1`, `source` and
`links`. Its additive `provider_records` object has up to four record kinds:

| Kind | Original object retained |
| --- | --- |
| `google_books` | A single Google Books volume item, including `volumeInfo`. |
| `open_library_search` | A single search document, with the existing requested field projection. |
| `open_library_work` | A validated work response that supplied a description. |
| `open_library_edition` | An exact-ISBN, language-validated edition response used for details refresh. |

Each kind contains a list of `{payload, fetched_at}` records. Objects are copied
before normalization; timestamps retain the source fetch time when known and are
null for old fixtures or callers without timing evidence. A merged candidate
retains distinct contributing objects within the bounded search, including later
objects that filled metadata gaps. It does not rewrite a work document to pretend
that it was an identified edition. Search-level ISBN/language inference retains
its existing limitations; keeping the document does not improve that inference.

These are original *book/work objects*, not full search-response envelopes or
request logs. Request headers, API credentials, client IPs and reader queries are
not added. Fields intentionally omitted from the existing Open Library request
cannot be recovered. Invalid or unused work responses are not presented as
evidence for a description.

`BookCandidate.provider_records` is excluded from public serialization and model
representation. The ranking formatter still sends only ISBN, title, authors and
description. Cards, detail responses and completed-result caches do not contain
original provider objects. Raw catalog responses retain their separate existing
24-hour Redis cache; this change adds durable per-book diagnostic evidence.

## Updates and compatibility

The normal fetch-time comparison still prevents older source-cache responses
from replacing newer snapshots. On an accepted newer write, a supplied provider
kind replaces that kind's list, rather than appending unlimited cross-search
history. Other kinds remain available. An absent/empty original-record collection
does not erase existing evidence. Details refresh follows the same merge rule and
the existing compare-and-update timestamp guard.

Unselected candidates receive static current store links without additional
retailer calls. A prior optional Apple Books match is retained only while the
incoming title and authors are unchanged. Selected cards use their actual channel
lookup result. Public detail reads regenerate and validate current channel rules.

Old rows and captures without `provider_records` remain valid. They acquire real
objects only on a subsequent catalog fetch; there is no invented backfill. A full
result-cache hit writes new search/result history without refreshing any book,
timestamp or provider object. No database migration, public API change, dependency
or provider change is required. The application signature changes normally, so
older parse/result cache keys become misses; no cache or usage key is cleared.

Older application code can read the additive envelope, but earlier writers can
discard its added field when replacing `raw`. Prefer a forward fix; preserve a
verified private backup before rolling application code back. The daily ledger
must remain intact under the [operations recovery rules](operations.md). No
automatic cleanup, retention deletion or provenance-history table is introduced.
Broader candidate storage and provider objects increase database/backup size;
production capacity and retention remain deployment work.

## Verification

Offline fixtures cover original-object copying, contributing-record merge,
description/edition validation, model/public/cache exclusion and unchanged public
normalization. Native PostgreSQL tests cover all-candidate storage, selected-only
results, atomic rollback, malformed unselected candidates, legacy rows, cache
replay, timestamp ordering and optional-link preservation. The 20 captured cases
are replayed with real foreign keys; this is not a fresh model quality evaluation.

For a real catalog-only storage probe, run from `backend/`:

```console
uv run python -m scripts.check_catalog_evidence --output evals/results/<new-report>.json
```

It requires local initialized PostgreSQL, calls the existing English/Spanish
catalog APIs without source-cache reuse, constructs explicitly synthetic
completed storage inputs with empty picks, and checks original objects/private
details in its own disposable schema. It records source failures and fails when
a language has no candidates. It neither runs the model/graph nor establishes
recommendation relevance, result-count quality or first-book latency. Public
table fingerprints and the shared AI count must remain unchanged. Reports never
overwrite earlier evidence; only the probe's own schema is removed.
