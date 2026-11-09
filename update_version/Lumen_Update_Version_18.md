# Lumen Update Version 18

## 1. Basic information

- **Round:** 18, an implementation round rather than a release version.
- **Date:** 2026-11-09, Europe/Madrid.
- **Branch:** `codex/update-18-catalog-evidence`.
- **Baseline:** local round-17 checkpoint `eaca768ded0d31ee584205b61b00bf3547ddd607` on `codex/update-17-durable-budget-and-backups`. Published `main` remained at round 16, `b91eb442de99ed5795ef517dad55d2a186649662`, while this work was implemented and verified.
- **Objective:** close the specification gaps in candidate-book coverage and original bibliographic response retention.
- **Actual scope:** persist all canonical, language-matched candidates of completed recommendation searches; retain original per-book/work provider objects privately; preserve transactional validation, cache replay, timestamp ordering, channels and existing detail reads. Add a live catalog-only diagnostic, regression coverage, documentation and sanitized evidence.
- **Dependency and sequencing:** this branch builds on the separately committed round 17. The user requested continuing directly and postponing their combined merge until this next round finished. No unrelated changes were present at branch creation, and round 17 was not merged early.

## 2. Technologies used

No new dependency, framework, provider or database table was introduced.

- **Pydantic:** `CatalogRecord` validates JSON-compatible original objects and optional timezone-aware fetch timestamps. The candidate's internal record collection is excluded from public/model/cache serialization and object representation.
- **Python copying and fixed record kinds:** original volume, search-document, work-description and edition objects are copied independently of response mutation. Merging retains distinct contributing objects within the already bounded search.
- **PostgreSQL JSONB and SQLAlchemy:** atomic JSONB overlays add the new evidence field to the existing snapshot envelope, replace supplied provider kinds and preserve absent kinds. Ordered ISBN upserts still share one transaction with the search and selected results.
- **httpx:** existing catalog clients retain the same requests and normalized metadata. The diagnostic calls both existing sources in both supported languages without model calls or source-cache reuse.
- **pytest, Ruff and Alembic:** offline tests, native database/cache tests, formatting/lint and migration/model agreement verify the actual behavior. Recorded-case replay remains distinct from fresh live recommendation evaluation.

## 3. Implementation

### Candidate coverage and selection remain separate

Previously, `save_completed` inserted only displayed cards. It now constructs book rows from all merged candidates in the completed state. Every candidate is rechecked for a canonical checksum-valid ISBN, matching supported language and nonblank title before writing. Duplicate candidate ISBNs remain invalid. Existing card membership, metadata, author, filter, explanation, rank and bounded-workflow validation is preserved.

Only the selected cards become `search_results`. A search with zero picks may still cache real retrieved books; a search with no candidates creates no books. Books, the anonymous search and its ordered recommendations still commit atomically. Conflicting ISBN language, duplicate search IDs, invalid input and cancellation cannot leave partial book rows or history. Sorted ISBN insertion retains consistent concurrent lock ordering.

No persistence was added to the legacy keyword JSON endpoint or unfinished/failed graphs. This defines the practical boundary of the specification's “books ever seen” within successfully completed recommendation searches.

### Original objects and fetch times

`BookCandidate.provider_records` holds lists for four fixed kinds: `google_books`, `open_library_search`, `open_library_work` and `open_library_edition`. A record contains the original copied `payload` and its known `fetched_at`, or null when the caller has no timing evidence. Google volume items, projected Open Library search documents, accepted work descriptions and validated exact editions retain their original structure instead of being reconstructed from normalized fields.

Later rounds can fill metadata gaps from different objects at the same provider, so merging keeps distinct contributing records during the bounded search. It does not rewrite a work's mixed-edition ISBN list to make it appear to be a verified edition. The existing search-level language inference limitations are unchanged.

The existing `books.raw` envelope retains version 1, source and links, and adds `provider_records`. Accepted newer writes replace each supplied kind's list; absent kinds remain available. This is not an unlimited cross-search history. Missing originals in older rows/captures are never fabricated. A newer snapshot's evidence cannot be overwritten by an older source-cache response. Targeted details refresh uses the existing compare-and-update guard and the same evidence overlay.

### Public and cache boundaries

Original objects are not sent to the ranking formatter, SSE cards, public detail responses or completed-result Redis snapshots. Ranking still sees only ISBN, title, authors and description. No full search-response envelope, request headers, credentials, IP or reader query is added to the catalog evidence.

Result-cache replay creates new search/result history without modifying books, originals or timestamps. Unselected candidates receive static links without retailer calls. A previous optional Apple Books match and its formats are retained only if title/authors remain unchanged; selected cards use their actual channel result. Public details continue to regenerate and validate current channel rules.

### Live diagnostic

`scripts.check_catalog_evidence` requires explicitly local PostgreSQL, reads the initialized shared budget, fingerprints public tables, and creates its own unique disposable schema. It fetches English and Spanish candidates from the existing catalog clients, merges them, supplies clearly labeled synthetic completed storage input with no picks, and verifies original-object equality and private detail serialization. It then checks public fingerprints and the real AI count and removes only its own schema. Reports use new paths and sanitize errors.

This diagnostic does not run the graph or model and does not evaluate semantic relevance, recommended counts or first-book latency. Its synthetic storage input is disclosed in both code and reports.

## 4. File changes

| File | Change and before/after behavior |
| --- | --- |
| `backend/app/sources/schemas.py` | Added internal typed original-record collections; public candidate metadata is unchanged. |
| `backend/app/sources/evidence.py` | Added independent original-object copying and source-fetch timestamp propagation. |
| `backend/app/sources/google_books.py` | Retains the original usable volume item alongside the same normalized fields and request parameters. |
| `backend/app/sources/open_library.py` | Retains the original usable projected search document; selection, fields and language/ISBN heuristics are unchanged. |
| `backend/app/sources/descriptions.py` | Retains an accepted validated work response when it supplies a description; lookup bounds and description handling remain unchanged. |
| `backend/app/sources/edition.py` | Retains original validated edition/volume objects during exact-ISBN refresh without changing lookup or rejection rules. |
| `backend/app/sources/merge.py` | Carries distinct contributing originals across the existing gap-filling merge without changing normalized winners or ordering. |
| `backend/app/repository.py` | Saves all validated candidates, selected-only result rows and private originals atomically; overlays compatible evidence and preserves optional channel matches for unchanged unselected books. |
| `backend/tests/test_catalog_evidence.py` | Added six offline tests for copying, work evidence, merge/timing, cache/public/model exclusion, description evidence and edition validation. |
| `backend/integration_tests/test_catalog_evidence.py` | Added eleven native cases for candidate coverage, zero candidates, four invalid unselected inputs, replay preservation, legacy/refresh evidence, timestamp replacement and two identity/channel cases. |
| `backend/integration_tests/test_persistence.py` | Updated catalog counts for all-candidate storage while retaining selected-only result counts, rollback/new-row coverage, foreign-key checks and private HTTP reads. |
| `backend/integration_tests/test_author_persistence.py` | Distinguishes cached candidates from the single valid-author recommendation; author validation remains required. |
| `backend/integration_tests/test_book_refresh.py` | Keeps the focused single-book setup explicit and checks the extended compatible raw envelope. |
| `backend/integration_tests/test_cache_usage.py` | Updates book-count expectations while retaining timestamp, budget and result-replay assertions. |
| `backend/integration_tests/test_replay_and_stream.py` | Checks all retrieved ISBNs across the 20 captured cases while preserving every selected result and real foreign key. |
| `backend/scripts/check_catalog_evidence.py` | Added the real catalog-only disposable persistence diagnostic described above. |
| `backend/evals/results/catalog-evidence-20261109-round18.json` | Retained the initial incomplete probe: both English sources responded, but the synthetic parsed input omitted its required genre. The schema was cleaned. |
| `backend/evals/results/catalog-evidence-20261109-round18-final.json` | Retained the first complete real API/storage probe after correcting that diagnostic input. |
| `backend/evals/results/catalog-evidence-20261109-round18-verified.json` | Added the final complete receipt matching the final diagnostic code, including source statuses, runtime hashes and unchanged public/budget fingerprints. |
| `backend/evals/results/catalog-compatibility-20261109-round18.json` | Added six fixture/language comparisons against round 17: normalized public data, ranking text and merged public metadata are identical. |
| `docs/catalog-storage.md` | Added coverage, record format, privacy/serialization, compatibility, growth/rollback limits and diagnostic instructions. |
| `README.md` | Replaces the former displayed-only/raw-data limitation with actual candidate and original-object behavior and documentation links. |
| `Lumen_Specifications.md` | Clarifies completed-search candidate coverage and the implemented compatible private raw envelope; no core capability or evaluation threshold changes. |
| `update_version/Lumen_Update_Version_18.md` | Added this round's detailed implementation, verification and submission record. |

No files were deleted. The frontend, prompts, graph selection flow, model/provider configuration, dependency locks and database schema were not changed in this round.

## 5. Project benefits

The saved catalog now reflects retrieved candidates rather than only the model's selections. Diagnostics can inspect the actual provider objects behind normalized fields and later gap filling. Unselected books can be read through the existing detail endpoint after a completed search. Stronger validation protects the newly widened storage input, while atomic writes and foreign keys continue to protect recommendation integrity. Evidence remains private and adds no model requests or retailer lookups.

## 6. Future impact

- There is no round-18 migration, API incompatibility or new service. Round 17's approved initialization/recovery requirements still apply.
- Existing books remain readable and gain authentic originals only on subsequent fetches. There is no historical backfill or claim of unavailable metadata.
- The application signature changes normally, producing old parse/result cache misses; no cache or allowance key was cleared.
- More candidates and original objects increase database and backup size. There is no automatic retention deletion, additional history table or production capacity claim.
- Older readers accept the additive raw envelope, but older writers can discard the added field. Prefer a forward fix and preserve verified private backups before code rollback; never roll back or reset the daily ledger as part of this change.
- Deployment packaging, controlled proxy setup, backup scheduling/off-host policy, documentation/media polish and public acceptance remain separate work.

## 7. Verification

| Check | Actual result |
| --- | --- |
| Final native offline backend suite | **372 passed**, 6.74 seconds. |
| Final native PostgreSQL/Redis suite | **64 passed**, 26.99 seconds, using disposable schemas/key namespaces. |
| Additional HTTP-exclusion assertion | **1 passed**, 0.53 seconds, after tightening the final test assertion. |
| Frontend stream/details regression suite | **11 passed**; existing nonfatal Node module-type warnings retained. No frontend code changed. |
| Ruff lint and format | Passed; **106 Python files** already formatted. |
| Alembic model agreement | Passed: no new upgrade operations detected. Round-17 revision remains the head. |
| Six baseline fixture/language comparisons | Passed: public normalized fields, ranking text and merged public metadata match `eaca768`. |
| Twenty captured cases with real PostgreSQL foreign keys | Passed within the 64-test suite, now checking all candidate ISBN rows and selected-only result rows. This is replay, not a new live AI gate. |
| Final actual catalog-only probe | Complete: Google Books and Open Library returned HTTP 200 for both languages; **8 English / 9 Spanish merged candidates** stored with equal original objects and private detail output. No source-cache reuse. |
| Live database/allowance preservation | Public tables unchanged: 225 books, 74 searches, 404 results; real shared daily use remained **61/100**. Only the temporary diagnostic schema was removed. |
| Local preview after restart | Backend health, English/Spanish home pages and an existing saved-book API response returned HTTP 200; provider originals remained absent from HTTP details. |

An initial implementation of JSONB indexing on a bound parameter caused seven refresh integration failures; using PostgreSQL's explicit JSON extraction operator fixed the issue, and the full suite passed afterward. The original diagnostic's missing required genre produced the retained incomplete report; it was corrected without altering application validation. Final lint also caught loop-variable closures in the diagnostic; bound provider calls fixed them, and a new successful real receipt matches the final code. The earlier lint log remains outside the repository under the local round-18 check directory. Failures were not hidden by lowering checks.

The full offline suite initially stalled under restricted Windows process execution and was stopped; the reported successful runs used the project's normal native execution permissions. No live AI requests were made, no daily limit was raised and no real usage counter was reset. Prompts, request parameters, ranking inputs and candidate selection are unchanged, so this storage-only delta does not invoke a new 20-query live recommendation gate. A new live run is still mandatory for future prompt/retrieval changes. Hosted CI, upload and merge are separate from these local results and must be verified during submission. No public deployment or production backup schedule is claimed.

## 8. Approvals and remaining work

No new major technical decision was required: the round implements the existing specification within the approved stack, sources and schema. The already approved PostgreSQL daily ledger and 100-attempt cap are preserved. No free-reading restoration, relevance/count relaxation, additional provider or production purchase was introduced.

The user requested deferring the prior merge until this next task was complete and then handling the pending rounds together. Round 17's record describes its earlier local-only checkpoint; this record explains the dependency and subsequent submission sequence without rewriting that historical record. Release, production deployment, paid services and off-host retention decisions remain unapproved and unperformed.

## 9. GitHub submission

**Commit title**

`feat: retain retrieved candidates and original catalog evidence`

**Commit description**

Completed searches previously cached only selected books, and books.raw retained normalized links rather than original bibliographic objects. Persist every canonical language-matched candidate of a completed recommendation search while keeping search_results limited to validated selected cards. Preserve atomic rollback, foreign keys, timestamp ordering and cache replay semantics.

Retain copied Google Books volume and Open Library search/work/edition objects in an additive private JSONB envelope. Keep originals out of model input, public responses and completed-result caches; preserve absent provider evidence and optional channel matches for unchanged unselected books. Keep the public API, schema, request parameters, prompts, selection flow, providers and daily 100-attempt limit unchanged. Document storage growth, old-writer rollback limits and deployment follow-up.

Validation: 372 offline, 64 native database/cache and 11 frontend tests passed; lint/format and Alembic model agreement passed. Six baseline fixture comparisons preserved public metadata and ranking text. All 20 captured cases persisted with real foreign keys. Actual uncached catalog-only checks saved 8 English and 9 Spanish candidates in disposable storage with equal originals, unchanged public tables and shared AI use of 61/100. No fresh model-quality/latency result or public deployment is claimed.

See `update_version/Lumen_Update_Version_18.md` and `docs/catalog-storage.md`. This branch depends on the separately committed round 17 described in `update_version/Lumen_Update_Version_17.md`; the pending rounds are submitted together only after round 18 is complete, as requested.

**Status at local checkpoint preparation:** implementation, verification and this record are complete. Neither pending branch has yet been pushed or merged at the time of writing. The user's combined-after-completion instruction controls the submission sequence; actual push/hosted-CI/merge outcomes are reported separately after execution. No release, collaborator or deployment action is included.
