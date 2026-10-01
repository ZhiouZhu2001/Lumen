# CLAUDE.md

## Authorship and attribution
- ZhiouZhu2001 is the sole author and distributor of this project.
- Never list Claude or Anthropic as an author, co-author, contributor, maintainer or distributor anywhere: source files, LICENSE, README, package metadata or docs.
- Do not add `Co-Authored-By: Claude ...` or any other Claude/Anthropic trailer to commit messages.
- Do not add "Generated with Claude Code" or similar lines to pull request descriptions, issues or comments.

## Git
- Do not create pull requests unless explicitly asked.
- Never force-push or rewrite history on `main`.

## Project
Lumen is an AI book-picking assistant. A user describes what they want to read; Lumen returns 5–10 **real** English or Spanish books and shows where to buy or read them in Spain. The full spec (in Chinese) is `Lumen_Specifications.md`; follow it.

Core rule: the AI may only choose from books retrieved from real bibliographic APIs. Never let it invent titles. Every recommended ISBN must be in the retrieved candidate list (checked in code and enforced by a DB foreign key).

MVP excludes: login, personalization, Chinese books, live price scraping, AI ratings, multi-turn chat.

## Stack
- Frontend: Next.js (App Router), TypeScript, shadcn, Zustand, next-intl (`en`, `es`)
- Backend: FastAPI, Pydantic, async httpx
- AI orchestration: LangGraph; LangChain only for model wrappers and structured output
- Data: PostgreSQL + SQLAlchemy + Alembic; Redis for cache and rate limiting
- Deploy: Docker Compose, Caddy, GitHub Actions

## Layout
- `frontend/` — `app/[locale]/`, `components/`, `stores/`, `lib/sse.ts`, `messages/{en,es}.json`
- `backend/app/` — `api/`, `graph/` (LangGraph), `sources/` (Google Books, Open Library, Gutendex, iTunes clients), `stores.yaml` (bookstore link rules), `models.py`, `cache.py`
- `backend/alembic/`, `backend/evals/`, `backend/tests/`
- `docker-compose.yml`, `Caddyfile`, `Makefile`

## Commands
- `make dev` — run the stack locally
- `make test` — pytest unit tests
- `make eval` — 20-query eval set; all 6 checks must pass before merging prompt or retrieval changes

## Conventions
- LangGraph is a fixed graph, not a free agent: one branch ("enough candidates?"), max 2 retries.
- Only `parse_query`, `broaden` and `rank_and_explain` call the model, always with Pydantic structured output.
- `rank_and_explain` sees at most 30 candidates (ISBN, title, authors, description). Reasons may only use facts from the description and are written in the UI language.
- Merge books by ISBN-13; drop books without an ISBN.
- Model names come from environment variables. Secrets live in `.env` (never committed); keep `.env.example` updated.
- API: `POST /api/search` (SSE: `status`, `candidates`, `book`, `done`, `error`), `GET /api/books/{isbn13}`, `GET /api/health`.
- Error codes: `rate_limited` (429), `no_results`, `upstream_unavailable`, `llm_failed`. Log structured with `search_id`.
- Rate limit: 20 searches per IP per hour, IP stored only in Redis. Daily AI call cap via env var.
- Unit tests cover real logic only (ISBN merge, store rules, rate limiting, retry condition) and use recorded API fixtures, no live network.
- Disable response buffering for SSE in Caddy.
