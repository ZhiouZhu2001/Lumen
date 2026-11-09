# Lumen Project Specification

Oct 1, 2026 · @ZhiouZhu

Approved scope revision, 2026-11-08: retire the unavailable Gutendex search
integration and temporarily remove free-only/public-domain reading from the MVP.
The user explicitly approved both the capability removal and its evaluation scope
change. Retain the previous suite and failed reports as historical evidence;
restoring free reading requires a reliable verified source and a new evaluation.
The current suite still contains 20 queries (10 per language) and all six checks.
Ordinary adventure classics replace the two former free-only scenarios.

A second user approval on 2026-11-08 classifies the English and Spanish
Spanish-author/decade/short-length scenarios as niche requests. All their reading
constraints remain in place. They may return 1–4 matching books only after both
broadening retries are exhausted, and the web interface must explain the limited
result. Ordinary queries still require 5–10; nonsense inputs require zero. This
is an explicit scope decision, not a retrospective pass for the failed runs.

Approved operational revision, 2026-11-09: the daily 100-attempt AI allowance
is stored in a PostgreSQL singleton containing only the current UTC date and
cumulative attempts. Client IP admission stays in expiring Redis keys. New
installations require explicit verified initialization; existing installations
import usage while AI workers are paused. Restore/rollback must preserve usage;
unknown recovered usage blocks new AI until reconciliation or UTC reset.

## 1. Overview

Lumen is an AI book-picking assistant: the user describes the kind of book they want to read, and Lumen returns 5–10 **real** English or Spanish books and tells the user where to buy or read them in Spain.

**Target users**: readers living in Spain who read English or Spanish books and know what genre they want, but not which specific book.

**Project positioning**: a portfolio project, built to real production standards, launched within 4 weeks.

**Core selling points** (what makes it different from just asking ChatGPT):

- Every book comes from a real bibliographic database; the AI can only choose from the retrieved candidates and cannot make up titles
- Every book comes with buying and reading options: physical bookstores, Kindle, Apple Books
- Every book shows the publisher's description, a rating from a real source (with the source labeled), and an AI-written reason for recommending it based on the user's request

**Out of scope for the MVP**: user login, personalized recommendations, Chinese books, live price scraping, AI ratings, multi-turn conversation.

## 2. Feature Scope

With a single input, the user sees the first recommended book within 15 seconds, and results stream in one book at a time.

**User flow**

1. Choose the book language at the top of the page: English or Español (the interface language switches with it)
2. Type a request in the text box, e.g. "fast-paced Spanish thriller with twists"
3. Optional filters: genre, publication era, length (short / medium / long)
4. Click search; the page shows progress: understanding your request → found N candidates → picking
5. Recommendation cards appear one by one

**Each recommendation card contains**

| Field | Source |
| --- | --- |
| Cover, title, author, publication year, page count | Google Books / Open Library |
| Format tags: paper / Kindle / Apple Books | Data source fields + inference from link rules |
| Publisher description (original text, collapsible) | Google Books |
| Rating + number of ratings + source name; "No rating yet" if none | Google Books / Open Library |
| Why we recommend it to you (2–3 sentences) | AI, based only on the book's real data |
| Buy and read buttons | Bookstore link rules |

**Bilingual interface**: next-intl provides two sets of copy, `en` and `es`. The book-language preference and the interface language are saved in localStorage and Zustand, and persist across reloads.

## 3. System Architecture

&#91;embedded content: Lumen system architecture · 5 containers, 5 external services\]

The browser only talks to Caddy; all external API and AI calls are centralized in the backend, so keys are never exposed to the frontend.

**Tech stack responsibilities**

| Layer | Technology | Responsible for |
| --- | --- | --- |
| Frontend | Next.js (App Router), TypeScript, shadcn, Zustand, next-intl | Pages, receiving SSE, saving language preference |
| Backend | FastAPI, Pydantic, httpx (async) | Endpoints, parameter validation, calling external APIs |
| AI orchestration | LangGraph; LangChain only for model wrappers and structured output | Search flow |
| Data | PostgreSQL, SQLAlchemy, Alembic | Books and search records |
| Cache | Redis | Caching, rate limiting |
| Deployment | Docker Compose, Caddy, GitHub Actions | Running and continuous integration |

**Repository structure**

```text
lumen/
├── frontend/
│   ├── app/[locale]/        # Pages, routed by language
│   ├── components/          # Book cards, search box, filters
│   ├── stores/              # Zustand: language preference, search state
│   ├── lib/sse.ts           # SSE client
│   └── messages/            # en.json, es.json
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routes
│   │   ├── graph/           # LangGraph state, nodes, graph definition
│   │   ├── sources/         # Google Books, Open Library, iTunes; legacy Gutendex retained
│   │   ├── stores.yaml      # Bookstore link rules
│   │   ├── models.py        # SQLAlchemy models
│   │   └── cache.py         # Redis caching and rate limiting
│   ├── alembic/
│   ├── evals/               # Eval queries and check scripts
│   └── tests/
├── docker-compose.yml
├── Caddyfile
├── Makefile                 # make dev / make test / make eval
└── README.md
```

## 4. LangGraph Flow

This is a fixed graph, not a free-form agent. In the refinement approved by the user on 2026-11-06, its single branch runs after ranking and validation ("are there enough validated recommendations?"), with at most 2 broadening retries. The flow is `parse -> search -> rank and validate -> finish or broaden -> search`. It stops when at least five valid matching recommendations are available or the retry budget is exhausted.

&#91;embedded content: LangGraph search graph · 6 nodes, 1 retry loop\]

Preserve valid picks across rounds, and prioritize retained picks and newly retrieved candidates within the 30-book ranking limit. After 2 retries, return the valid subset even if fewer than five remain; return `no_results` if the model validly chose none. Persistently malformed nonempty model output remains `llm_failed`. Model/provider and upstream failures retain their separate error paths. A successful first round uses two logical model invocations; the maximum is six: one parse, two broadenings and three rankings. No unbounded repair loop is allowed.

**Graph state**

```python
class SearchState(TypedDict):
    query: str
    language: Literal["en", "es"]
    filters: Filters
    parsed: ParsedQuery | None   # output of parse_query / broaden
    candidates: list[Book]       # candidates after merge, deduplicated by ISBN
    retries: int                 # number of retries so far, max 2
    picks: list[Pick]            # [{isbn13, rank, reason}]
    results: list[BookCard]      # final cards with buy links
```

The approved implementation also retains validation feedback, newly retrieved
ISBNs, logical model-call counts and per-round ranking evidence. Initial parsing
identifies whether the input has meaningful reading intent. Unintelligible input
returns no results without catalog requests or broadening; it must not be turned
into an invented generic reading request. This does not reject uncommon but
meaningful topics, names or genres.

**Rules**

- Only the `parse_query`, `broaden` and `rank_and_explain` nodes call the AI, all with Pydantic structured output; the other nodes are plain Python code
- The `rank_and_explain` prompt only receives each candidate's ISBN, title, authors and description, for at most 30 books; after it returns, code filters out any ISBN not in the candidate list
- Recommendation reasons may only cite information from the description, and are written in the user's interface language
- Use LangGraph's `astream` to turn node progress into SSE `status` events
- Each node's duration and AI usage are written to structured logs, tagged with `search_id`
- Model names live in environment variables, so switching models requires no code changes

## 5. Data Sources and Purchase Channels

Bibliographic data comes only from public APIs. Bookstores only answer "where to buy", with links generated from the ISBN; the MVP does not scrape prices.

**Bibliographic data sources**

| Data source | Purpose | Key fields |
| --- | --- | --- |
| Google Books API | Primary search source, supports `langRestrict=en/es` | ISBN, description, cover, page count, `averageRating`, `saleInfo.isEbook` |
| Open Library API | Supplementary search and ratings | ISBN, work id, ratings (ratings endpoint) |
| iTunes Search API (`media=ebook`) | Check whether Apple Books has the book | Product link |

Merge rule: deduplicate using ISBN-13 as the primary key; books without an ISBN are dropped, so every book is traceable.

**Bookstore link rules** (`backend/app/stores.yaml`; adding a store means adding one config entry)

| Bookstore | Language | Genre | Format | Link method |
| --- | --- | --- | --- | --- |
| Amazon.es | en, es | All | Paper + Kindle | URL template searching by ISBN |
| Apple Books | en, es | All | Ebook | Link returned by the iTunes Search API; hidden if not found |
| Casa del Libro | es | All | Paper + ebook | URL template searching by ISBN |
| Abacus | es | All | Paper | URL template searching by ISBN |
| Norma Comics | es | Comics, manga, graphic novels | Paper | URL template searching by ISBN or title |

Each URL template is manually verified once in week 3 and written into the test script. Casa del Libro has an affiliate program on Awin (5% base commission); after launch you can apply and switch its links to affiliate links. [Source](https://ui.awin.com/merchant-profile-terms/21491)

## 6. Database Design

The MVP has three core bibliographic/search tables, all created with Alembic migrations. The operational revision approved on 2026-11-09 adds the `ai_daily_usage` singleton for durable model-attempt protection. Book data is cached by ISBN, and search records are stored anonymously for use by personalized recommendations in phase two.

**books**: one row per canonical, language-matched candidate seen in a completed recommendation search. All such candidates are cached, including those not recommended; only selected books enter `search_results`. Failed/cancelled searches do not write partial records, and the compatible keyword JSON endpoint remains read-only.

| Column | Type | Notes |
| --- | --- | --- |
| isbn13 | char(13) PK | Primary key, format validated before insert |
| title, authors | text, text\[\] | Not null |
| language | char(2) | `en` or `es`, CHECK constraint |
| description | text | Publisher description |
| cover\_url | text | Nullable |
| page\_count, published\_year | int | Nullable |
| genres | text\[\] | Used to match genre rules such as Norma Comics |
| rating\_value, rating\_count, rating\_source | numeric(2,1), int, text | All three null or all three set (CHECK) |
| formats | text\[\] | `paper` / `kindle` / `apple_books`; `free` is retained for historical compatibility but not emitted by active channels |
| raw | jsonb | Compatible snapshot envelope plus private original book/work API objects, for debugging; no reader input or request credentials |
| fetched\_at | timestamptz | Re-fetched after 30 days |

**searches**: one row per search

| Column | Type | Notes |
| --- | --- | --- |
| id | uuid PK |  |
| query\_text | text | The user's original input |
| parsed\_query | jsonb | Structured query parsed by the AI |
| language | char(2) |  |
| filters | jsonb |  |
| candidate\_count, retries | int | How many candidates were found and how many retries were made |
| duration\_ms | int | For monitoring performance |
| created\_at | timestamptz | Indexed |

No personally identifying information such as IP addresses is stored.

**search\_results**: which books each search recommended

| Column | Type | Notes |
| --- | --- | --- |
| search\_id | uuid FK → searches |  |
| isbn13 | char(13) FK → books |  |
| rank | smallint | Display order |
| reason | text | AI-written recommendation reason |

The primary key is (search\_id, isbn13). The foreign key constraint guarantees at the database level that "every recommended book is in the books table" — the last line of defense against fabrication.

**ai_daily_usage** (approved operational addition): one row with `id = 1`, `utc_day` and nonnegative `attempts`. It contains no client identity, query or per-request history. A committed atomic reservation precedes every outbound model attempt, including SDK retries. The same current-day total cannot be lowered by initialization. Missing/future-dated state or unavailable storage fails closed. At the natural UTC rollover the single row advances; previous daily rows are not retained in the live table.

## 7. API Endpoints

The backend exposes only 3 endpoints; the core one is a search endpoint that returns an SSE stream.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/search` | Accepts the request, returns `text/event-stream` |
| GET | `/api/books/{isbn13}` | Single book details (for share links) |
| GET | `/api/health` | Checks Postgres and Redis connectivity, for deployment monitoring |

**`POST /api/search` request body** (validated by Pydantic)

```json
{
  "query": "fast-paced Spanish thriller with twists",
  "language": "es",
  "filters": { "genre": "thriller", "era": "2000s", "length": "medium", "free_only": false }
}
```

`query` is limited to 3–300 characters; `language` can only be `en` or `es`.

The web client requests SSE with `Accept: text/event-stream`. For compatibility,
requests without that header retain the earlier keyword JSON response. Nonempty
filters on the JSON path are rejected instead of ignored. `free_only: false`
is accepted for compatibility, while `true` is rejected with HTTP 422 under the
approved scope revision. Publication decades mean inclusive ten-year ranges
(e.g. 2010s = 2010–2019); short = at most 200 pages, medium = 201–400, long =
over 400. Missing metadata excludes a book from that metadata constraint. Open Library
work descriptions may be fetched from validated work identifiers, with at most
eight lookups per search and three concurrent requests, to supply real catalog
evidence for constrained results; failure never creates a description. Genre
conditions guide semantic retrieval and ranking; they are not inferred solely
from inconsistent catalog category labels.

**SSE events** (pushed in order)

| Event | Data | Frontend behavior |
| --- | --- | --- |
| `status` | `{stage: "parsing" \| "searching" \| "ranking"}` | Progress indicator |
| `candidates` | `{count: 34}` | "Found 34 candidates" |
| `book` | Full card data for one book + `reason` + `links` | Append one card |
| `done` | `{search_id, total}` | End the loading state |
| `error` | `{code, message}` | Friendly error message |

Error codes are defined centrally: `rate_limited` (429), `no_results`, `upstream_unavailable`, `llm_failed`. All errors are written to structured logs, tagged with `search_id`.

## 8. Caching and Rate Limiting

Redis caches repeated requests and admits at most 20 searches per client IP per hour. The durable global AI attempt budget is enforced separately in PostgreSQL.

| Key | Content | TTL |
| --- | --- | --- |
| `parse:{sha256(query+language+filters)}` | Structured query parsed by the AI | 7 days |
| `gbooks:{sha256(params)}` | Raw Google Books response | 24 hours |
| `olib:{sha256(params)}` | Raw Open Library response | 24 hours |
| `result:{sha256(query+language+filters)}` | Final result of the whole search | 6 hours |
| `rl:{ip}:{yyyymmddhh}` | Number of searches from this IP this hour | 1 hour |

**Rate limit rule**: at most 20 searches per IP per hour; beyond that, return 429. IPs exist only in Redis, expire automatically after 1 hour, and are never written to PostgreSQL.

**Global safeguard**: `DAILY_AI_CALL_CAP=100` limits committed outbound model-attempt reservations per UTC day, including provider retries, using the shared PostgreSQL singleton. The API, live evaluations and provided live teaching tools share this ledger. Exhaustion returns a maintenance notice for uncached work; missing initialization or storage outages stop new model requests. A reservation is not refunded after failure/cancellation. This is an attempt limit, not a token or currency accounting system. Restoring old data requires reconciliation or blocking the current day before AI workers resume.

On a `result:` cache hit, results are still pushed one book at a time over SSE, so the frontend doesn't need to distinguish the two cases.

## 9. Testing and Quality

Run `make eval` after every change to prompts or retrieval logic; all 6 checks must pass before merging.

**Eval query set**: `backend/evals/queries.yaml`, 20 queries in total, 10 in English and 10 in Spanish, covering:

- Broad genres ("fantasy with dragons")
- Requests with constraints ("short stories, after 2010, Spanish author")
- Comics (to verify the Norma Comics link rule)
- Adventure classics (replacing retired free-only cases under the approved scope revision)
- Niche requests (to verify the retry branch)
- 2 nonsense inputs (should return `no_results`, not invented books)

**Automated checks**

| Check | Pass criterion |
| --- | --- |
| Authenticity | Every recommended book's ISBN is in this search's candidate list |
| Correct language | Every book's `language` matches the request |
| Count | Normal queries return 5–10 books; niche queries (including the two approved multi-constraint cases) may return 1–4 only after two retries; nonsense input returns 0 |
| Link rules | Spanish books have no English-only channels; non-comic books have no Norma Comics link |
| Recommendation reason | Not empty, and contains no proper nouns beyond those in the `description` and title (simple heuristic check) |
| Latency | The first book is pushed within 15 seconds |

**Unit tests** (pytest) only cover places with real logic: ISBN merging and deduplication, bookstore rule matching, rate limit counting, and the retry condition. External APIs are replaced by recorded responses as test doubles; unit tests never hit the real network.

## 10. Deployment

A single VPS runs all 5 services with Docker Compose. Local development and production use the same compose file, differing only in environment variables.

| Service | Image | Notes |
| --- | --- | --- |
| caddy | caddy:2 | Reverse proxy with automatic HTTPS; forwards `/api/*` to backend and everything else to frontend |
| frontend | Custom (Next.js standalone build) | Port 3000 |
| backend | Custom (FastAPI + uvicorn) | Port 8000; runs `alembic upgrade head` before starting |
| postgres | postgres:16 | Persistent data volume, daily backup with `pg_dump` |
| redis | redis:7 | Volatile cache/IP admission; losing it cannot reset the PostgreSQL AI budget |

**Key points**

- Response buffering must be disabled for SSE passing through Caddy, otherwise streaming won't work
- Secrets (AI API key, Google Books key, database password) live in a `.env` file on the VPS and are never committed; the repository provides `.env.example`
- GitHub Actions runs lint, unit tests and type checks on every push; deployment is done manually at first with `git pull && docker compose up -d --build`, and automated once stable
- Buy a domain (about €10 per year) and put the live URL in the README

## 11. Four-Week Plan

6 days a week, 3–4 hours a day, about 21 hours per week. Every weekend there must be a demoable version; if something can't be finished, cut the feature rather than slip the schedule.

### Week 1: Get retrieval working without AI

- [ ] Set up the monorepo; `docker compose up` starts Postgres, Redis, backend and frontend
- [ ] Create the 3 tables with Alembic
- [ ] Implement the Google Books and Open Library clients, merging and deduplicating by ISBN
- [ ] `POST /api/search` first searches directly by keyword and returns plain JSON
- [ ] Frontend: language switch, search box, book card list (shadcn)
- [ ] Unit tests for merging and deduplication

**Done when**: typing English keywords shows real books.

### Week 2: Add AI and streaming

- [ ] Wrap the model call layer (LangChain, structured output)
- [ ] Build the 5 nodes and the retry branch in LangGraph
- [ ] The picking node can only output ISBNs from the candidate list, verified again in code
- [ ] Switch to SSE; the frontend shows cards and progress messages one by one
- [ ] Bilingual interface with next-intl

**Done when**: describing a request in one natural-language sentence streams results with recommendation reasons.

### Week 3: Channels, caching, quality

- [ ] `stores.yaml` link rules, plus iTunes Search lookups (Gutendex retired by the approved scope revision)
- [ ] Manually verify each bookstore's URL template
- [ ] Redis caching and IP rate limiting, plus the daily AI call cap
- [ ] 20 eval queries and the `make eval` script, iterated until all pass
- [ ] Filters take effect

**Done when**: all 6 `make eval` checks pass.

### Week 4: Launch and polish

- [ ] Rent a VPS, buy a domain, configure Caddy, complete deployment
- [ ] GitHub Actions runs the tests
- [ ] Polish the UI: loading skeletons, empty states, error messages, mobile layout
- [ ] README: what problem it solves, screenshots and GIFs, architecture diagram, technical trade-offs, how to run locally
- [ ] Record a 2-minute demo video
- [ ] Have 3 friends try it and record their feedback

**Done when**: a stranger can open the link and use it, and the README clearly explains why it was designed this way.

## 12. Later Phases and Risks

After the MVP launches, consider phase two: user accounts, "read / liked" markers, history-based personalized recommendations (the already-stored `searches` and `search_results` can be reused directly), and applying for Casa del Libro affiliate links.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Google Books has poor coverage of Spanish books | Too few Spanish results | Supplement with Open Library; track Spanish queries separately in the eval set; relax the retry condition if needed |
| A bookstore redesign breaks a URL template | Links return 404 | Every template has an eval case; when one breaks, hide only that channel without affecting the whole card |
| AI-written reasons exaggerate or invent plot details | Undermines the "real books" selling point | Prompt limits reasons to description content; heuristic checks in evals; the page labels "Reason generated by AI" |
| External API quota limits or outages | Searches fail | Redis caching; return `upstream_unavailable` with a friendly message |
| AI costs spiral | Over budget | IP rate limiting + daily call cap |
| Scope creep | Can't finish in 4 weeks | A demoable version every weekend; all new ideas go on the phase-two list |
