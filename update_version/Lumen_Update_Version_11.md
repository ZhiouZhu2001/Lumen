# Lumen Update Version 11

## 1. Basic information

- **Date:** 2026-11-08 (Europe/Madrid).
- **Branch:** `codex/update-11-search-persistence`.
- **Baseline:** `bc9abff8aa6b62e4dc3ee70f1d3ed3086eeb1d11`, verified on remote `main` and `codex/update-10-search-preview` before this branch was created.
- **Objective:** connect completed recommendation searches to the existing PostgreSQL tables and implement the specified single-book API.
- **Actual scope:** transactional persistence, defensive snapshot validation, saved-book reads, application wiring, offline/native-database tests, limited live verification and documentation. No schema, dependency, prompt, retrieval, model-provider or frontend changes.
- **Starting state:** clean working tree after publication of Update 10. Existing public tables contained zero books, searches and results. No unrelated user edits were included.

The user authorized uploading and merging the previous round, then starting the next round. Update 10 was uploaded and fast-forward merged into `main`: implementation commit `cff3b7a87b0fad02bfebdd38cb173ae09b9477b4`, followed by publication-record commit `bc9abff8aa6b62e4dc3ee70f1d3ed3086eeb1d11`. The remote branch and `main` were verified at the latter commit. No pull request, release or production deployment was created.

## 2. Technologies used

No new technology or dependency was introduced.

- **SQLAlchemy async engine and asyncpg:** reuse the configured PostgreSQL connection pool for short transactions and reads.
- **PostgreSQL:** `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`, existing foreign keys and check constraints keep books and ordered results consistent. Sorted ISBN insertion provides a consistent lock order for overlapping searches.
- **FastAPI and Pydantic:** validate the ISBN path and public `BookDetails` response, including a timezone-aware snapshot timestamp.
- **Existing LangGraph/SSE boundary:** persistence runs after validated cards are streamed and before successful completion, without holding a transaction during model or catalog calls.
- **pytest, pytest-asyncio and httpx:** exercise failure paths, HTTP contracts, native transactions and recorded search cases. Native integration tests use uniquely named disposable schemas in the local PostgreSQL instance.
- **Ruff and SHA-256 fingerprints:** check source conventions and bind retained verification reports to the application bytes used.

## 3. Implementation

### Completed searches and atomic writes

The application lifespan now creates one `SearchRepository` using the existing engine. The actual search API requires this repository; the optional repository argument on the stream class supports isolated tests and standalone diagnostics, rather than a storage bypass in the running API.

The flow is now:

1. Run the existing bounded graph and emit progress/candidate events.
2. Build and emit each validated recommendation card with its existing channel rules.
3. Validate the complete final snapshot again at the storage boundary.
4. In one short transaction, upsert the displayed books, insert the anonymous search and insert its ordered recommendations.
5. Commit before emitting `done`.

Expected empty results also persist a search with zero recommendations, including meaningful searches that exhaust both retries and unintelligible inputs that require no catalog requests. Model/source failures and incomplete searches are not recorded as completed searches. The original query, latest structured query, filters, total retrieved candidate count, retries and processing duration are stored on the search. The recorded duration is measured before the final database write, so it excludes transaction completion time.

Storage validation rejects unknown or noncanonical ISBNs, changed candidate metadata, wrong languages, metadata-filter violations, partial/reordered picks, altered reasons, invalid ranks and unfinished retry flows. It reuses the established pick validation and compares the card's public bibliographic fields with its retrieved candidate. Internal work identifiers are excluded from public serialization.

Only displayed, validated books are written in this round. Unselected candidates contribute to `candidate_count` but are not yet cached. Each recommendation is linked to its book and search by the existing foreign keys. Query-specific reasons and ranks stay in `search_results`; they are not copied into public book snapshots.

### Book updates and provenance

An existing ISBN is updated without erasing optional metadata when the latest candidate has null values. Empty author/genre lists preserve existing values. Rating value, count and source are updated together, or all preserved when no incoming rating exists. The latest formats and normalized provenance replace their previous snapshots. A conflicting language for an existing ISBN fails the whole transaction instead of silently relabeling earlier search history.

`books.raw` currently contains `snapshot_version: 1`, the normalized source identifier and public channel links. It contains neither original provider payloads nor reader requests, reasons, ranks, search IDs, IP addresses or user-agent data. This is a bounded implementation of provenance storage; the specification's full provider-payload debugging cache remains unfinished. `fetched_at` marks the saved validated book snapshot, not an independently refreshed source fetch.

Any duplicate search ID, foreign-key failure or SQL error rolls back the transaction, including book changes made earlier in that transaction. Cancellation before commit also rolls back. Cancellation after a successful commit cannot undo already saved data. Database failures produce a sanitized stream error before the normal termination event; cards already streamed can remain visible, but the stream does not claim that saving succeeded. Writes share the existing 60-second stream deadline. No database credentials or exception text are returned.

### Saved-book endpoint

`GET /api/books/{isbn13}` now:

- Rejects invalid length, nondigits, ISBN-10 and invalid checksums with 422 before accessing storage.
- Returns 404 for a valid ISBN that has not been saved.
- Returns saved bibliographic metadata, a source rating when present, active channel links/formats and `fetched_at` for a saved ISBN.
- Excludes search IDs, original requests, recommendation reasons/ranks and raw storage fields.
- Returns a sanitized 503 when storage is unavailable or a stored row cannot be represented safely.

Static store links are regenerated from current rules. Versioned saved Apple Books links are reused only when their store, HTTPS host and title/author-match type satisfy the active rule. Labels and formats come from the current rule. Unknown, malformed, unsafe and retired free-reading links are ignored. Apple matches remain work-level evidence, without language/edition or stock guarantees.

Only known Google Books/Open Library provenance identifiers are exposed from legacy raw fields; unknown values use `catalog_cache`. This final read-path hardening was added after the three live searches and verified by the final tests and restart checks.

GET performs no model or external catalog requests and does not refresh `fetched_at`. It is a backend endpoint; the frontend detail/share page and automatic 30-day refresh are not implemented here. Existing keyword JSON search behavior remains read-only and compatible.

## 4. File changes

| File | Change and before/after behavior |
| --- | --- |
| `backend/app/repository.py` | Added the validated transactional save and safe saved-book read boundary; previously the stream had no persistence implementation. |
| `backend/app/api/books.py` | Added the specified GET endpoint, checksum validation and sanitized 404/503 responses. |
| `backend/app/channels/schemas.py` | Added `BookDetails` with links, formats and an aware timestamp, without request-specific recommendation fields. |
| `backend/app/main.py` | Creates the repository from the existing engine and registers the book router during application setup. |
| `backend/app/api/search.py` | Supplies the application's repository to recommendation streams; legacy JSON handling is unchanged. |
| `backend/app/search_stream.py` | Saves completed snapshots after card emission and before termination; sanitizes storage failures. |
| `backend/tests/persistence_fixtures.py` | Adds recorded bibliographic fixtures for valid completed snapshots without external requests. |
| `backend/tests/test_persistence_stream.py` | Tests save ordering, empty results, sanitized failures, model failure and cancellation. |
| `backend/tests/test_books_api.py` | Tests invalid ISBN rejection before storage and sanitized storage errors. |
| `backend/integration_tests/__init__.py` | Defines the explicit native-database test package. |
| `backend/integration_tests/conftest.py` | Creates and removes only each test's uniquely named PostgreSQL schema; public tables are left intact. Supports optional `LUMEN_TEST_DATABASE_URL`. |
| `backend/integration_tests/test_persistence.py` | Tests native transactions, upserts, rollback, conflicts, validation, foreign keys, privacy, current channel rules, concurrent saves, cancellation and GET responses. |
| `backend/integration_tests/test_replay_and_stream.py` | Persists all 20 previously captured search cases with real foreign keys and tests API-to-repository wiring. |
| `backend/evals/results/persistence-smoke-20261108.json` | Retains three actual frontend/API/database smoke checks, timings, row counts and source fingerprints. Explicitly marks `full_suite: false`. |
| `backend/evals/results/persistence-restart-20261108.json` | Retains ten successful saved-book reads after backend restart, final source fingerprints and the earlier failed readiness probe. |
| `README.md` | Documents persisted completion, saved-book reads, native-database testing and the remaining implementation boundary. |
| `update_version/Lumen_Update_Version_11.md` | Adds this round's implementation, verification and proposed submission record. |

No files were deleted. Models, migrations, lockfiles, prompts, source clients and frontend files were unchanged.

## 5. Project benefits

Recommendations now survive a backend restart and have a durable search/result relationship. Real foreign keys and a second validation boundary prevent arbitrary or partial recommendation snapshots from becoming completed records. Atomic writes avoid orphaned searches/results and partially updated books after errors. Shared book metadata remains separate from request-specific explanations, allowing the single-book endpoint to serve a reusable public snapshot. Reads make no paid model calls.

The repository centralizes storage behavior instead of embedding SQL in the graph or HTTP routes. Native integration tests verify PostgreSQL behavior, including concurrent writes and cancellation, that mocks alone would not establish.

## 6. Future impact and compatibility

- **Actual API change:** additive saved-book GET endpoint and persistence on completed SSE searches. Existing request/response fields, SSE buffering headers and legacy keyword JSON behavior are retained. Saving can now fail explicitly when PostgreSQL is unavailable.
- **Database:** existing three tables and constraints only; no migration or reset. Live verification left 10 books, 3 searches and 10 results in the local public tables. All temporary test schemas were removed.
- **Dependencies/deployment:** no new dependencies, services or configuration requirements for the application. Normal startup still requires the existing migrations and a working PostgreSQL instance.
- **Privacy:** no IP/user-agent/account fields were added to PostgreSQL. Original reading requests remain in the specified anonymous search table, so users should still avoid entering personal information into requests. The public GET response does not expose them.
- **Performance:** the transaction follows card emission, preserving the existing first-card path. This does not establish future concurrency throughput or a production latency guarantee.
- **Possible later work:** Redis result/source caches must retain provenance and must not turn cache hits into misleading fresh catalog timestamps. A 30-day refresh mechanism, storage of unselected candidates/full provider payloads, a share/detail UI, retention operations and deployment checks still need implementation or explicit design work.

## 7. Verification

All commands below were run from `backend/` against the final production source, except the live smoke capture whose one later read-only change is identified below.

| Check | Actual result |
| --- | --- |
| `uv run python -m pytest -q` | **271 passed**, final run 10.39 seconds; offline unit suite. |
| `uv run python -m pytest -q integration_tests` | **21 passed**, final run 8.28 seconds; actual local PostgreSQL with isolated schemas. |
| `uv run ruff check app scripts tests evals integration_tests` | Passed. |
| Native persistence of the previous successful 20-case capture | All 20 cases persisted and all saved ISBNs read successfully inside an isolated PostgreSQL schema; included in the 21 integration tests. This is recorded-data replay, not new model/catalog execution or latency measurement. |
| Three real searches through the running frontend | Passed: constrained Spanish request saved 1 book, English fantasy request saved 9, nonsense input saved an empty search with expected `no_results`. SQL records and all 10 detail responses matched the streamed books. |
| Actual first-card timings for the two nonempty smoke searches | 12,459.36 ms and 4,345.51 ms through the frontend. The empty request has no first-book timing. |
| Restart durability | Backend restarted; all 10 saved books returned 200 through the frontend afterwards. Final readiness took 2,109 ms within a 30-second check window. |
| Local service health | Direct backend and frontend-forwarded health returned 200 with PostgreSQL/Redis healthy after final restart. |
| Public data/isolation check | 10 books, 3 searches, 10 results; zero remaining `lumen_test_*` schemas. Existing public data was not reset. |
| Final source/evidence check | All 44 application/evaluation fingerprints matched the final restart report; its smoke-report SHA-256 reference also matched. |
| Formatting and submission-content checks | All 13 Python files in this round passed `ruff format --check`. `git diff --check` passed; all 17 changed/new files passed trailing-whitespace, repository-language, attribution and configured-secret checks. |

The live smoke report was captured before the final legacy-provenance whitelist. Comparing its fingerprints with the final restart capture identifies only `app/repository.py` as changed. That change sanitizes unknown legacy source values on reads; query processing and database writes are unchanged. The final unit/native tests and all ten restarted detail reads cover the final source. The restart report also links the smoke report by SHA-256.

An earlier readiness probe (30 attempts with a 0.25-second pause) ended during startup while tests were running concurrently and failed. Later startup logs showed completion and both health routes returned 200. The final bounded restart check passed; the earlier failure remains recorded rather than being presented as a successful run. An earlier restricted unit-test invocation also stalled and was terminated after verifying the owned process; the normal final invocation completed with all 271 tests passing.

**Omitted checks:** no new full 20-query live evaluation was run because this round changes neither prompts nor retrieval. The complete successful live gate from Update 10 remains historical evidence for that baseline; database replay and three new smoke queries do not replace or relabel it. Frontend lint/build/browser interaction checks were not repeated because frontend files and behavior were unchanged. No production, load or 30-day freshness test was performed.

## 8. Approvals and remaining work

There was no new major technical decision. This implements already specified PostgreSQL persistence and the single-book API with the existing tables and stack. The previously approved free-only removal and niche-result rules remain unchanged. No new paid service, recurring service cost, model provider, public deployment or schema change was introduced.

Remaining priorities are shared Redis caches, the specified 20-per-IP hourly limit, the global daily AI-call safeguard, catalog refresh and the frontend book-detail/share view. Production launch remains pending. The existing lexical reason/relevance checks and bibliographic language hints retain their documented limitations; passing persistence tests does not establish complete semantic accuracy.

## 9. GitHub submission

**Proposed commit title**

`feat: persist validated searches and expose saved book details`

**Proposed commit description**

Completed recommendation searches previously disappeared when the backend stopped, and the specified single-book endpoint was unavailable. Persist displayed validated books, anonymous searches and ordered recommendations atomically before stream completion, and serve reusable book details without exposing the reader's request or reason.

Add a repository over the existing three-table schema, exact snapshot validation, metadata-preserving ISBN upserts, language-conflict rollback, sanitized storage failures and current-rule channel reconstruction. Preserve the keyword JSON API, bounded graph, model-call limits, filters and existing SSE behavior. No migrations or dependencies are added.

Validation: 271 offline tests and 21 native PostgreSQL tests passed, including rollback, foreign keys, concurrency, cancellation, API wiring and database replay of all 20 recorded evaluation cases. Three new real frontend searches saved ten recommendations and one expected empty search; all ten saved books remained readable after backend restart. These limited live checks are not a fresh full evaluation. Remaining work includes Redis caches, rate/daily safeguards, catalog refresh, a share/detail UI and production checks.

See `update_version/Lumen_Update_Version_11.md` for implementation details, exact verification boundaries, retained readiness failure, compatibility and future impacts.

**Actual status:** Update 10 is uploaded and merged as described above. Update 11 remains local on `codex/update-11-search-persistence`; upload confirmation has not been received for this new round. No Update 11 commit, push, pull request, merge, release or deployment has been performed.
