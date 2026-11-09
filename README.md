# Lumen

An English/Spanish book recommendation assistant for readers in Spain. Recommendations come from real bibliographic candidates with validated ISBNs, source metadata, explanations and reading/purchase channels.

The local preview supports streamed progress and cards, genre guidance, strict publication-decade/page-count filters, and explicit feedback when bounded searches find fewer matches. Free-only reading is temporarily unavailable under the approved scope revision.

## Run locally

The current setup was verified with Python 3.12, Node 24, uv and Docker Desktop.

1. Copy `.env.example` to `.env` and configure the database, Redis and existing API credentials. Keep `.env` private.
2. From the repository root, start the data services:

   ```console
   docker compose up -d --wait postgres redis
   ```

3. In a backend terminal:

   ```console
   cd backend
   uv sync --locked
   uv run alembic upgrade head
   # Initialize/import the daily budget as described below before first API start.
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-proxy-headers
   ```

4. In a frontend terminal:

   ```console
   cd frontend
   npm ci
   npm run dev -- --hostname 127.0.0.1 --port 3000
   ```

Before the first API start, follow the [budget and recovery runbook](docs/operations.md). For a verified new installation with no prior model use, initialize with `uv run python -m scripts.budget_admin initialize --used 0 --confirm-ai-workers-stopped --output ../backups/budget-init.json` from `backend/`. For an existing installation, stop every AI worker and use `import-redis` instead. A missing legacy counter conservatively blocks the day; it is never assumed to mean zero. Existing initialized installations do not repeat initialization.

Open [Spanish](http://127.0.0.1:3000/es) or [English](http://127.0.0.1:3000/en). A production build can be checked locally with `npm run build` followed by `npm run start -- --hostname 127.0.0.1 --port 3000`.

The frontend forwards `/api/*` to port 8001 by default. Its server-side `BACKEND_URL` configuration can select another backend. Searches request SSE using `Accept: text/event-stream`; older requests without that header retain keyword JSON. Store searches do not establish stock or edition availability.

Completed recommendation streams save their validated books, anonymous search record and ordered recommendations in one PostgreSQL transaction before `done`. Expected empty results also save a search record. The legacy keyword JSON path remains read-only. `GET /api/books/{isbn13}` returns a saved book's metadata, current channel rules and snapshot timestamp, without the reader's request or recommendation reason; an ISBN that has not been saved returns 404. Fresh snapshots are read directly. Snapshots at least 30 days old receive a bounded exact-ISBN catalog refresh on access, without calling the model.

After a recommendation search finishes successfully, each card offers a details/share link. Open `/es/books/{isbn13}` or `/en/books/{isbn13}` to read a saved book, switch interface language while retaining its ISBN, and copy its public link. The book's original catalog language is displayed separately. Sharing includes only the current origin, interface language and ISBN, with a selectable link when automatic copying is unavailable. Local preview links work only on the machine running the preview; sharing across devices requires a reachable deployment.

Details are rendered on the server using the same server-side `BACKEND_URL` setting, with a five-second read timeout and no persistent frontend data cache. Invalid ISBNs, missing saved books and temporary read failures receive separate localized messages; temporary failures include a full-page retry. These streamed page states can return HTTP 200 even when the underlying API returns 404/422/503; the page is not an HTTP-status or rich social-preview implementation. A snapshot date identifies the catalog fetch, not current store stock; failed refreshes retain the old date.

An old saved snapshot is refreshed only from the same canonical ISBN and language. Google Books is preferred, with an identified Open Library edition as fallback; work-level ISBN/language lists cannot identify a replacement edition. The entire optional attempt has a three-second deadline, three refresh slots per backend process and one expiring Redis attempt lease per ISBN for five minutes across workers. Source outages, missing language evidence, unavailable coordination or rejected writes retain the old snapshot and date. Only an existing book can be updated, and a conditional timestamp check protects a concurrent newer save. Search history is unchanged. Missing optional metadata is preserved; an old Apple Books title/author match is retained only if those effective identity fields are unchanged. This is refresh on access, not a scheduled sweep of unopened books.

## Caches and usage limits

Redis shares parsed requests for seven days, successful Google Books/Open Library JSON for 24 hours, and completed recommendation snapshots for six hours. Search keys include the exact request, language and normalized filters; parse/result keys also include the configured model and application/rule version. Invalid cache entries become misses. HTTP errors are not cached as successful catalog responses. Apple Books retains its existing process-local optional-lookup cache.

Result hits still stream individual cards and create new anonymous search/result records. They make no model or retailer calls, do not overwrite newer book metadata and do not advance the stored catalog timestamp. Source-cache hits retain the actual source-fetch timestamp as well. The saved-detail endpoint now refreshes snapshots at least 30 days old on access; successful refresh preserves the actual source-fetch timestamp, including a catalog-cache hit. A failed refresh never makes an old snapshot look newly fetched.

Both search response modes allow 20 admitted searches per client IP per UTC clock hour, including cache hits; excess requests return 429 with `Retry-After`. IP identifiers exist only in expiring Redis usage keys, not PostgreSQL. `DAILY_AI_CALL_CAP=100` limits actual outbound model HTTP attempts per UTC day, including failed provider retries, across API workers and provided live tools using the same PostgreSQL ledger. A full result hit remains available when the AI budget is exhausted, subject to the hourly limit. Uncached AI requests receive a maintenance response; exhaustion during a stream emits an error. Optional cache operations can fail as misses. Unavailable Redis admission blocks new searches, and unavailable or uninitialized PostgreSQL budget storage blocks new model work.

Run Uvicorn with `--no-proxy-headers`, as the backend Docker entry point does. `TRUSTED_PROXY_IPS` defaults to an empty JSON array, so arbitrary forwarding headers cannot supply an identity. A controlled production reverse proxy must overwrite or safely append the real forwarding chain; configure only its exact IPs/CIDRs in this setting. With no trusted proxy configured, forwarded preview traffic shares the proxy's socket IP limit. Do not trust a public client's supplied header or configure a network containing untrusted clients. Production proxy routing still needs verification.

The daily counter limits request attempts, not tokens or currency. The provided live model teaching scripts share the durable allowance through owned budgeted clients; they do not use the HTTP per-IP admission limit. Redis data loss loses caches and hourly counters but not the daily AI ledger. PostgreSQL data loss or restoring an older dump requires reconciliation; never resume AI from an unverified old count. Private public-schema dumps and isolated restore checks are available through `uv run python -m scripts.backup_database` from `backend/`. See the operations runbook for paused-service migration, conservative recovery and daily scheduling/retention boundaries. Concurrent identical cold requests can still perform duplicate work within the enforced budget.

## Continuous integration

The [CI workflow](.github/workflows/ci.yml) runs on pushes and pull requests. Manual dispatch is available after the workflow reaches the default branch. It publishes two independent checks:

- **Backend checks:** install Python from `backend/.python-version` and locked development dependencies with uv 0.12.15; check Ruff lint/formatting; apply Alembic migrations to a fresh PostgreSQL 17 service; verify migration/model agreement; run offline unit tests and the native PostgreSQL/Redis integration suite.
- **Frontend checks:** install Node 24 and dependencies with `npm ci`; run ESLint and native tests; build the production Next.js application, including its TypeScript checks.

Both jobs use Ubuntu 24.04 runners and a 15-minute timeout. PostgreSQL/Redis services and the public `ci_only` password are temporary test resources. The jobs do not require project secrets: model/catalog keys are empty, and live recommendation evaluation and catalog diagnostics remain separate explicit commands. The daily setting remains 100; CI does not spend the normal model allowance.

Action versions are pinned to verified full commits, checkout credentials are not persisted, and the workflow token has read-only repository contents access. Dependency caches are keyed from the lockfiles. A newer run for the same branch or pull request cancels the older in-progress run. These checks report failures; making `Backend checks` and `Frontend checks` mandatory for merging requires a separate branch-protection setting. The workflow does not configure deployment or automatic merging.

Local reproduction uses the commands below. A successful local run is separate evidence from a GitHub-hosted run; confirm the first hosted run after uploading a new workflow.

## Verification

From `backend/`, run `uv run python -m pytest -q` and `uv run ruff check app scripts tests evals integration_tests`. From `frontend/`, run `npm test`, `npm run lint` and `npm run build`. The native stream-parser tests require Node TypeScript-stripping support.

Run the explicit PostgreSQL integration checks from `backend/` with `uv run python -m pytest -q integration_tests`. They use the configured local database, or `LUMEN_TEST_DATABASE_URL` when supplied, and require permission to create schemas. Each test creates and removes its own uniquely named schema; the public tables are left intact. These checks include atomic rollback, foreign keys, concurrent saves, cancellation, API wiring and persistence of all 20 previously captured evaluation cases. Replaying captured cases is separate from a fresh live evaluation and does not measure new model quality or latency.

`make eval` runs 20 real English/Spanish searches through a loopback backend and retains candidate evidence and actual first-book HTTP timings. It uses the configured APIs and model. To include the running frontend's forwarding/compression path, keep the frontend running, stop the standalone backend on port 8001, and run from `backend/`:

```console
uv run python -m evals.run --live --frontend-url http://127.0.0.1:3000 --backend-port 8001
```

The evaluator owns its temporary backend on that port and closes it after the run; restart the normal backend afterwards. See [evaluation documentation](backend/evals/README.md) for report replay, approved niche-case criteria and historical suites.

The frontend proxy timeout is 70 seconds so it can carry the backend's 60-second search deadline and terminal SSE frames. This does not relax the 15-second first-book requirement. A delayed protocol comparison is available in `scripts/check_proxy_stream.py`; it starts a temporary diagnostic backend and makes no model/catalog calls. A cache-aware isolated evaluation helper in `scripts/run_isolated_eval.py` keeps hourly test counters separate while charging every actual model attempt to the normal shared daily budget.

To verify saved-book refresh separately, run `uv run python -m scripts.check_book_refresh --output evals/results/<new-report>.json` from `backend/`. It requires local PostgreSQL/Redis and two already-saved reference ISBNs, copies only their public book rows into a disposable schema and ages those copies. Real catalog calls must refresh both copies, preserve their public originals and leave search-history/model-usage counters unchanged. A supplementary live Open Library fallback probe simulates only the Google Books failure. Existing reports are never overwritten; the tool cleans only its own schema and Redis key namespace. This diagnostic verifies catalog freshness, not new recommendation quality.

## Current boundary

Explicitly requested authors are retained from the original request, checked against catalog author metadata before ranking and checked again before streaming, cache reuse and persistence. Names match conservatively with case/accent normalization and catalog surname-first notation; this does not establish pseudonym or abbreviated-name identity. Comparisons, books about a person and nationality requests do not become positive named-author filters. A single requested author stays in broadened catalog searches. The two supplementary author regressions can be run with `uv run python -m evals.author_run --output evals/results/<new-report>.json` from `backend/` against the running preview; they do not replace the required full 20-case gate.

The preview is local development work. Production deployment/proxy setup and off-host backup/scheduling policy remain to be completed. The daily budget now persists independently of Redis, with verified import and guarded recovery tools. The bilingual book-detail/share UI reads saved snapshots and refreshes old ones on access; unopened books are not swept by a scheduler. Rich social previews and HTTP-status-aware detail pages remain separate polish work. PostgreSQL currently stores displayed validated books rather than every unselected candidate; `books.raw` contains a versioned normalized public snapshot rather than original provider payloads. Lexical checks, parsed author intent and catalog metadata do not prove every semantic reading constraint or author identity. The original wrong-author snapshot, interrupted evaluation and completed cache-aware 20-case retry are retained with their verification boundaries. Implementation records and submission descriptions are in [update_version](update_version/).
