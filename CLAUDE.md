# CLAUDE.md

## Project execution rules

- Read and follow the root `AGENTS.md` for the implementation workflow, automatic per-round branches, mandatory records in `update_version/Lumen_Update_Version_<N>.md`, user approval before major changes, and explicit confirmation before GitHub pushes.
- These rules supplement the project conventions below.

## Repository language

- Use English as the primary language for uploaded code, identifiers, comments, docstrings, project documents, configuration explanations, update records, commit titles and bodies, and GitHub descriptions.
- Preserve intentional English/Spanish localization, original bibliographic text, and language-specific queries or fixtures required by the specification.
- Write all new update records in English and check changed files and submission text for compliance before uploading. Conversation replies may use the user's preferred language.

## Authorship and attribution
- ZhiouZhu2001 is the sole author and distributor of this project.
- Never list Codex, OpenAI, Claude, Anthropic, any other AI tool or any other person as a project author, co-author, collaborator, contributor, maintainer or distributor in source files, LICENSE, README, package metadata, update records or other project content.
- Do not add any `Co-Authored-By` trailer or assistant attribution to commit titles, commit bodies, GitHub descriptions, pull requests, issues or comments.
- Do not add "Generated with ...", "Assisted by ..." or similar attribution or acknowledgements.
- Before committing or uploading, verify the author and committer identities and review pending content for unwanted attribution. Use the user's verified Git identity; never invent a name or email. Do not add GitHub collaborators without explicit user authorization.

## Git
- Before each implementation round, create and switch to a new local `codex/` branch as specified in `AGENTS.md`.
- Prepare a clear commit title and description covering the problem, changes, validation and impact. Include the description in the commit body when uploading.
- Push only after the user explicitly confirms the reviewed round and branch. Keep unrelated working-tree changes out of the submission.
- Do not create pull requests unless explicitly asked.
- Never force-push or rewrite history on `main`.

## Project
Lumen is an AI book-picking assistant. A user describes what they want to read; Lumen returns 5–10 **real** English or Spanish books and shows where to buy or read them in Spain. The full spec is `Lumen_Specifications.md`; follow it.

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
- LangGraph is a fixed graph, not a free agent: one branch after ranking ("enough validated recommendations?"), max 2 broadening retries. The user approved this refinement on 2026-11-06; retain valid picks and prioritize newly retrieved candidates within the 30-book limit. At most one parsing call, two broadening calls and three ranking calls are allowed per search (six logical model invocations).
- Only `parse_query`, `broaden` and `rank_and_explain` call the model, always with Pydantic structured output.
- `rank_and_explain` sees at most 30 candidates (ISBN, title, authors, description). Reasons may only use facts from the description and are written in the UI language.
- Merge books by ISBN-13; drop books without an ISBN.
- Model names come from environment variables. Secrets live in `.env` (never committed); keep `.env.example` updated.
- API: `POST /api/search` (SSE: `status`, `candidates`, `book`, `done`, `error`), `GET /api/books/{isbn13}`, `GET /api/health`.
- Error codes: `rate_limited` (429), `no_results`, `upstream_unavailable`, `llm_failed`. Log structured with `search_id`.
- Rate limit: 20 searches per IP per hour, IP stored only in Redis. Daily AI call cap via env var.
- Unit tests cover real logic only (ISBN merge, store rules, rate limiting, retry condition) and use recorded API fixtures, no live network.
- Disable response buffering for SSE in Caddy.
