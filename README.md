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
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8001
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

## Verification

From `backend/`, run `uv run python -m pytest -q` and `uv run ruff check app scripts tests evals integration_tests`. From `frontend/`, run `npm test`, `npm run lint` and `npm run build`. The native stream-parser tests require Node TypeScript-stripping support.

Run the explicit PostgreSQL integration checks from `backend/` with `uv run python -m pytest -q integration_tests`. They use the configured local database, or `LUMEN_TEST_DATABASE_URL` when supplied, and require permission to create schemas. Each test creates and removes its own uniquely named schema; the public tables are left intact. These checks include atomic rollback, foreign keys, concurrent saves, cancellation, API wiring and persistence of all 20 previously captured evaluation cases. Replaying captured cases is separate from a fresh live evaluation and does not measure new model quality or latency.

`make eval` runs 20 real English/Spanish searches through a loopback backend and retains candidate evidence and actual first-book HTTP timings. It uses the configured APIs and model. To include the running frontend's forwarding/compression path, keep the frontend running, stop the standalone backend on port 8001, and run from `backend/`:

```console
uv run python -m evals.run --live --frontend-url http://127.0.0.1:3000 --backend-port 8001
```

The evaluator owns its temporary backend on that port and closes it after the run; restart the normal backend afterwards. See [evaluation documentation](backend/evals/README.md) for report replay, approved niche-case criteria and historical suites.

## Current boundary

The preview is local development work. Shared Redis caches/rate limits, the daily AI-call cap, 30-day catalog refresh, a frontend book-detail/share page and production deployment checks remain to be implemented. PostgreSQL currently stores displayed validated books rather than every unselected candidate; `books.raw` contains a versioned normalized public snapshot rather than original provider payloads. The lexical grounding and relevance checks do not prove every semantic reading constraint. Implementation records and submission descriptions are in [update_version](update_version/).
