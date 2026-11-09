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
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-proxy-headers
   ```

4. In a frontend terminal:

   ```console
   cd frontend
   npm ci
   npm run dev -- --hostname 127.0.0.1 --port 3000
   ```

Open [Spanish](http://127.0.0.1:3000/es) or [English](http://127.0.0.1:3000/en). A production build can be checked locally with `npm run build` followed by `npm run start -- --hostname 127.0.0.1 --port 3000`.

The frontend forwards `/api/*` to port 8001 by default. Its server-side `BACKEND_URL` configuration can select another backend. Searches request SSE using `Accept: text/event-stream`; older requests without that header retain keyword JSON. Store searches do not establish stock or edition availability.

Completed recommendation streams save their validated books, anonymous search record and ordered recommendations in one PostgreSQL transaction before `done`. Expected empty results also save a search record. The legacy keyword JSON path remains read-only. `GET /api/books/{isbn13}` returns a saved book's metadata, current channel rules and snapshot timestamp, without the reader's request or recommendation reason; an ISBN that has not been saved returns 404. This endpoint reads stored snapshots without calling the model or external catalogs.

## Caches and usage limits

Redis shares parsed requests for seven days, successful Google Books/Open Library JSON for 24 hours, and completed recommendation snapshots for six hours. Search keys include the exact request, language and normalized filters; parse/result keys also include the configured model and application/rule version. Invalid cache entries become misses. HTTP errors are not cached as successful catalog responses. Apple Books retains its existing process-local optional-lookup cache.

Result hits still stream individual cards and create new anonymous search/result records. They make no model or retailer calls, do not overwrite newer book metadata and do not advance the stored catalog timestamp. Source-cache hits retain the actual source-fetch timestamp as well. The database's automatic 30-day refresh remains future work.

Both search response modes allow 20 admitted searches per client IP per UTC clock hour, including cache hits; excess requests return 429 with `Retry-After`. IP identifiers exist only in expiring Redis usage keys, not PostgreSQL. `DAILY_AI_CALL_CAP=100` limits actual outbound model HTTP attempts per UTC day, including failed provider retries, across API workers using the same Redis database. A full result hit remains available when the AI budget is exhausted, subject to the hourly limit. Uncached AI requests receive a maintenance response; exhaustion during a stream emits an error. Optional cache operations can fail as misses, but unavailable Redis usage checks block new search work.

Run Uvicorn with `--no-proxy-headers`, as the backend Docker entry point does. `TRUSTED_PROXY_IPS` defaults to an empty JSON array, so arbitrary forwarding headers cannot supply an identity. A controlled production reverse proxy must overwrite or safely append the real forwarding chain; configure only its exact IPs/CIDRs in this setting. With no trusted proxy configured, forwarded preview traffic shares the proxy's socket IP limit. Do not trust a public client's supplied header or configure a network containing untrusted clients. Production proxy routing still needs verification.

The daily counter limits request attempts, not tokens or currency. Standalone model diagnostic scripts are outside the HTTP admission boundary. Redis data loss also loses its counters; durable budget accounting across a Redis reset and production retention/backup behavior require follow-up before a public launch. Concurrent identical cold requests can still perform duplicate work within the enforced budget.

## Verification

From `backend/`, run `uv run python -m pytest -q` and `uv run ruff check app scripts tests evals integration_tests`. From `frontend/`, run `npm test`, `npm run lint` and `npm run build`. The native stream-parser tests require Node TypeScript-stripping support.

Run the explicit PostgreSQL integration checks from `backend/` with `uv run python -m pytest -q integration_tests`. They use the configured local database, or `LUMEN_TEST_DATABASE_URL` when supplied, and require permission to create schemas. Each test creates and removes its own uniquely named schema; the public tables are left intact. These checks include atomic rollback, foreign keys, concurrent saves, cancellation, API wiring and persistence of all 20 previously captured evaluation cases. Replaying captured cases is separate from a fresh live evaluation and does not measure new model quality or latency.

`make eval` runs 20 real English/Spanish searches through a loopback backend and retains candidate evidence and actual first-book HTTP timings. It uses the configured APIs and model. To include the running frontend's forwarding/compression path, keep the frontend running, stop the standalone backend on port 8001, and run from `backend/`:

```console
uv run python -m evals.run --live --frontend-url http://127.0.0.1:3000 --backend-port 8001
```

The evaluator owns its temporary backend on that port and closes it after the run; restart the normal backend afterwards. See [evaluation documentation](backend/evals/README.md) for report replay, approved niche-case criteria and historical suites.

The frontend proxy timeout is 70 seconds so it can carry the backend's 60-second search deadline and terminal SSE frames. This does not relax the 15-second first-book requirement. A delayed protocol comparison is available in `scripts/check_proxy_stream.py`; it starts a temporary diagnostic backend and makes no model/catalog calls. A cache-aware isolated evaluation helper in `scripts/run_isolated_eval.py` keeps hourly test counters separate while charging every actual model attempt to the normal shared daily budget.

## Current boundary

Explicitly requested authors are retained from the original request, checked against catalog author metadata before ranking and checked again before streaming, cache reuse and persistence. Names match conservatively with case/accent normalization and catalog surname-first notation; this does not establish pseudonym or abbreviated-name identity. Comparisons, books about a person and nationality requests do not become positive named-author filters. A single requested author stays in broadened catalog searches. The two supplementary author regressions can be run with `uv run python -m evals.author_run --output evals/results/<new-report>.json` from `backend/` against the running preview; they do not replace the required full 20-case gate.

The preview is local development work. Automatic 30-day catalog refresh, a frontend book-detail/share page and production deployment/proxy/budget-durability checks remain to be implemented. PostgreSQL currently stores displayed validated books rather than every unselected candidate; `books.raw` contains a versioned normalized public snapshot rather than original provider payloads. Lexical checks, parsed author intent and catalog metadata do not prove every semantic reading constraint or author identity. The original wrong-author snapshot, interrupted evaluation and completed cache-aware 20-case retry are retained with their verification boundaries. Implementation records and submission descriptions are in [update_version](update_version/).
