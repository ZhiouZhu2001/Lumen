# Lumen Update Version 10

## 1. Basic information

- Date: 2026-11-08, Europe/Madrid.
- Branch: `codex/update-10-search-preview`.
- Baseline: local Update 9 checkpoint `b6a1262`, based on main `a089ab4f036a123b3aca25526a83fa9b70dbd022`.
- The previously completed Update 9 was saved locally before this branch was created. That checkpoint and this round have not been uploaded. No unrelated user changes were present at the round boundary.
- Objective: retire an unavailable optional free-book source, verify real searches honestly, and start a usable local recommendation preview.
- Actual scope: five active reading/purchase channels; HTTP recommendation streaming; request filters; bounded catalog-description enrichment; literary/course separation; bilingual result cards; approved limited-result behavior; real HTTP evaluation and retained historical evidence.
- Status: implementation, real frontend-path evaluation, browser verification and local service startup completed. The user confirmed publication; implementation commit `cff3b7a87b0fad02bfebdd38cb173ae09b9477b4` was uploaded and fast-forwarded into GitHub main on 2026-11-08.

## 2. Technologies used

No new dependency or dependency version was introduced.

- FastAPI and Starlette `StreamingResponse` send SSE events from an asynchronous generator. The stream carries progress, candidate counts, complete validated cards, errors and completion.
- LangGraph `astream(..., stream_mode="updates")` exposes progress from the existing fixed graph. Only parsing, broadening and ranking call the model; the maximum remains two broadenings and six logical model invocations. SDK transport retries are not additional graph invocations and are not represented as billable-call counts.
- Pydantic validates metadata filters and compatibility fields. Publication dates and lengths are checked in Python before ranking and again when evaluating returned cards.
- Existing Google Books and Open Library APIs remain the bibliographic sources. Open Library accepts year/page range constraints and can supply genuine descriptions from validated work identifiers.
- Existing httpx/asyncio mechanisms bound optional lookups, description concurrency and the complete stream. No retailer prices are scraped.
- Next.js, React, TypeScript and next-intl display streamed recommendations in English/Spanish. Fetch, ReadableStream, TextDecoder and AbortController handle split UTF-8/SSE events and cancellation without another browser dependency.
- Native Node test tooling verifies the browser stream parser. Tests were run on Node 24; the test command requires a Node version supporting TypeScript stripping.
- Uvicorn and a real loopback HTTP client measure the first received book event. A private in-process observer retains candidate evidence without exposing an audit endpoint.
- Git attributes retain historical suite bytes so stored SHA-256 values survive checkout newline conversion.

## 3. Implementation

### Source retirement and approved scope

Gutendex search was probed again with a real query and timed out after five seconds. The user explicitly approved retiring that integration and temporarily removing free-only reading and its corresponding evaluation scope. The active store configuration now contains Amazon.es, Apple Books, Casa del Libro, Abacus and Norma Comics. The builder makes no Gutendex requests and rejects attempts to re-enable that lookup provider through configuration.

The legacy Gutendex client, fixtures, link schema values and old reports remain for historical reproducibility. Their presence does not mean free reading is available. `free_only: true` receives HTTP 422 rather than being silently interpreted as a paid-book request; `false` remains compatible. The web interface explains that free-only reading is unavailable. Ordinary adventure-classics queries replace the former free-only cases while keeping 20 distinct cases and ten cases per language.

The user subsequently approved treating the two Spanish-author/decade/short-length cases as niche scenarios. Their constraints remain intact. One to four books are acceptable only after both broadening retries are exhausted; the interface explicitly explains the limited result. Other normal queries still require five to ten books. Nonsense inputs require zero. Earlier failed captures are not relabeled as successful.

### Graph and catalog correctness

Validated filters are included in the reading request passed to parsing, broadening and ranking. Genre participates in semantic selection. A decade is an inclusive ten-year range; short is at most 200 pages, medium is 201–400, and long is over 400. Unknown dates/page counts do not satisfy selected constraints. Open Library also receives actual range parameters, rather than relying only on prompt wording.

Initial search guidance distinguishes author nationality from book language and permits controlled catalog-subject searches. Broadening can use at most five author names taken from already validated matching picks; it cannot seed searches with unsupported names from rejected reasons. Valid picks and new-candidate prioritization are retained, and ranking still sees at most 30 candidates with the established description limit.

A conservative reader-type check excludes clear language-course substitutions for literary requests. Explicit language-learning requests remain supported. The initial request genre is retained across broadenings, preventing a later genre change from bypassing that check. This heuristic does not prove author nationality, complete semantic relevance or factual grounding.

Browser review subsequently found reasons explicitly admitting that a requested subject was absent, such as conceding that a sea request was not centered on the sea. Production validation and the reason evaluation check now reject explicit English/Spanish concessions containing requested terms. Ordinary negation and positive "not only" constructions remain accepted. A rejected ISBN is excluded from later ranking rounds of the same search, preventing a rewritten reason from hiding the admission. The ranking prompt also makes the main subject/setting mandatory. This is a bounded lexical guard, not a complete semantic verifier; it adds no model call or retry.

Constrained searches may fill missing descriptions using at most eight distinct Open Library work lookups across the entire request, with three concurrent requests and two-second individual deadlines. Work paths and returned identifiers must match. Only actual nonempty string/text-object descriptions are accepted, capped at 12,000 characters. Failures leave evidence missing. Descriptions can fill already retrieved ISBN records linked to the same work; they do not create new recommendation identities. Internal work keys are excluded from public card serialization. Source title, ISBN, language and metadata are preserved.

### HTTP and browser behavior

`POST /api/search` uses graph/card SSE when the client sends `Accept: text/event-stream`. Requests without that header retain the existing keyword JSON path. Nonempty filters on the JSON path are rejected rather than ignored. This preserves compatibility while making the web interface use the recommendation flow.

The SSE stream reports parsing/searching/ranking progress and candidate counts, then enriches and emits each validated card before looking up the next. Later Apple request-spacing waits do not hold the entire batch ahead of the first card. Cards retain rank order, ISBN membership and grounding checks. Optional Apple failures hide that link while keeping applicable ISBN store searches. The complete stream is bounded at 60 seconds; provider/model errors have friendly codes and a terminal completion event. Cancellation propagates. No result rows are written in this round.

An additional real frontend-path check exposed gzip buffering: the rewrite held both status and book events until the complete response, with first delivery at 27.6 seconds despite passing direct-backend timing. The installed compression middleware honors `no-transform`; SSE now sends `Cache-Control: no-cache, no-transform` while normal page compression remains enabled. The existing forwarding structure is retained. A gzip-capable warm probe then received its first event at 59.37 ms, before completion at 930.85 ms, with no content encoding. A cold-start diagnostic took 1,308.91 ms to its first event and failed an exploratory 500-ms expectation; it is retained separately and is not represented as a failed or waived 15-second first-book product check.

The evaluator can now measure every case through an already running frontend via `--frontend-url` and a matching fixed `--backend-port`. It owns a privately observed loopback backend during that run, records response encoding/first event timing, and has no silent direct-backend fallback. The normal preview backend is restored afterwards.

The browser shows original metadata, rating/source, inferred format tags, recommendation reasons, collapsible catalog descriptions and purchase/reading links. It explains that store searches do not prove stock/format, and Apple work matching does not verify exact edition/language. Locale changes abort active searches and clear stale results. Controls have visible labels, busy state and progress/error announcements. Light colors are kept consistent to avoid unreadable combinations with the existing white controls.

Limited-result and page-count messages use ICU plural forms in both locales, including the single-book case exercised during browser review. The loading button keeps a short label while the separate status region explains the search stage.

The client parser supports split event delimiters, CRLF/LF, multibyte UTF-8 and multiline data. It rejects malformed JSON, non-SSE/failed responses and streams ending without completion. It does not silently mark a truncated response successful.

## 4. File changes

| File | Change and purpose |
| --- | --- |
| `.gitattributes` | Added exact-byte preservation for historical suite snapshots. |
| `README.md` | Documents actual local startup, checks, frontend-path evaluation and remaining production work. |
| `CLAUDE.md` | Records the two explicit scope approvals and the implemented compatibility/filter/lookup boundaries. |
| `Lumen_Specifications.md` | Updates active channels, free-only scope, constrained-case classification, filters and HTTP compatibility; retains planned work as planned. |
| `backend/app/api/search.py` | Adds the SSE path and validated filters while preserving keyword JSON behavior. |
| `backend/app/search_stream.py` | Added bounded progress/card streaming, sanitized errors, cancellation, limited-result metadata and a private evaluation observer. |
| `backend/app/filters.py` | Added validated filters, prompt context and strict year/page checks. |
| `backend/app/reading_intent.py` | Added conservative language-course rejection and explicit requested-topic concession detection. |
| `backend/app/book_cards.py` | Removes runtime Gutendex dispatch and rejects retired lookup-provider configuration. |
| `backend/app/stores.yaml` | Removes the active Gutenberg rule; five active channels remain. |
| `backend/app/channels/README.md` | Documents active channels, retirement, streaming and remaining matching/coordination limitations. |
| `backend/app/graph/state.py` | Adds optional filters, retained original genre and attempted description work keys. |
| `backend/app/graph/workflow.py` | Applies constraints before ranking, retains original intent, bounds enrichment, and supplies verified author seeds to broadening. |
| `backend/app/graph/parse_query.py` | Distinguishes nationality from language-learning queries and suggests controlled subject headings. |
| `backend/app/graph/broaden.py` | Uses verified catalog authors and encourages distinct wider searches without increasing the retry budget. |
| `backend/app/graph/rank.py` | Explicitly rejects language-course substitutes for literary requests. |
| `backend/app/graph/search.py` | Passes supported metadata constraints to Open Library. |
| `backend/app/sources/open_library.py` | Sends actual range parameters and retains validated internal work identifiers. |
| `backend/app/sources/descriptions.py` | Added bounded real work-description retrieval, identifier checks and missing-evidence fallback. |
| `backend/app/sources/schemas.py` | Adds an optional internal work key, excluded from serialization. |
| `backend/app/sources/merge.py` | Preserves a work key when filling missing metadata without replacing primary titles/identities. |
| `backend/evals/http_run.py` | Added real loopback HTTP evaluation, first-book timing, wire/card consistency and candidate-evidence capture. |
| `backend/evals/run.py` | Makes HTTP evaluation the default live mode; retains explicit graph-only diagnostics and adds enrichment/intent evidence fields. |
| `backend/evals/checks.py` | Removes retired mandatory free-case coverage and strengthens reason checking to reject explicit requested-topic concessions; historical free-link checks remain intact. |
| `backend/evals/queries.yaml` | Keeps 20 bilingual cases, replaces free-only cases with ordinary classics and marks the two approved multi-constraint cases niche. |
| `backend/evals/history/queries-update9.yaml` | Adds the exact original free-only suite used by the Update 9 report. |
| `backend/evals/history/queries-update10-strict.yaml` | Adds the exact strict-count suite used by the first two Update 10 HTTP reports. |
| `backend/evals/history/queries-update10-approved.yaml` | Adds the exact currently approved suite for final capture replay. |
| `backend/evals/README.md` | Explains real HTTP evidence, approved scope changes, historical suites, replay and remaining semantic limitations. |
| `backend/evals/results/eval-http-20261108-round10-initial.json` | Adds the first complete failed HTTP capture; Spanish constrained count failed. |
| `backend/evals/results/eval-http-20261108-round10-final.json` | Adds the second complete failed HTTP capture; English constrained count failed. The filename does not signify success. |
| `backend/evals/results/eval-http-20261108-round10-verified.json` | Retains the first passing approved-scope capture, before the additional issue found during browser review. |
| `backend/evals/results/eval-http-20261108-round10-semantic-verified.json` | Retains the backend-only capture after strengthening topic-mismatch validation, before the transport-header fix. |
| `backend/evals/results/proxy-sse-20261108-round10.json` | Retains the real failed frontend buffering probe instead of hiding it behind a backend-only timing pass. |
| `backend/evals/results/proxy-compression-fixed-20261108-round10.json` | Retains the warm no-transform probe and its separate cold-start diagnostic observation. |
| `backend/evals/results/eval-frontend-20261108-round10-final.json` | Retains the full real frontend-to-backend evaluation after the compression fix. |
| `backend/tests/test_book_cards.py` | Updates active-channel expectations; keeps cache, failure, rate-spacing, ISBN and mutation coverage. |
| `backend/tests/test_evals.py` | Updates retired free-case coverage expectations while retaining gate and historical-link checks. |
| `backend/tests/test_search_api.py` | Adds rejection of filters on the legacy JSON path. |
| `backend/tests/test_workflow.py` | Adds filtering-before-ranking, verified-author seeds, eight-lookups-per-request and preserved-reading-intent regressions. |
| `backend/tests/test_search_stream.py` | Adds filter-boundary, wire-order, error, cancellation and retired-provider regressions. |
| `backend/tests/test_descriptions.py` | Adds genuine description mapping, failed/mismatched evidence, path checks and source-range parameter coverage. |
| `backend/tests/test_reading_intent.py` | Covers clear courses, explicit language practice and ordinary literature/science. |
| `backend/tests/fixtures/open_library_work_description_live.json` | Adds selected public fields from a successful real Open Library work response. |
| `frontend/app/[locale]/page.tsx` | Replaces keyword JSON consumption with SSE; adds filters, progress, limited-result notice and stale-search cancellation. |
| `frontend/components/BookCard.tsx` | Adds reasons, page counts, inferred formats, description disclosure, actual channel buttons and readable empty-cover/rating contrast. |
| `frontend/app/globals.css` | Removes the inconsistent automatic dark-color override from this otherwise light interface. |
| `frontend/lib/types.ts` | Describes full streamed cards rather than only basic keyword-result metadata. |
| `frontend/lib/sse.ts` | Added incremental stream parsing and completion validation. |
| `frontend/messages/en.json`, `frontend/messages/es.json` | Add localized filters, progress, descriptions, channel caveats and limited-result copy. |
| `frontend/tests/sse.test.mjs` | Adds four native Node stream-parser tests. |
| `frontend/package.json` | Adds the test command; dependencies and versions are unchanged. |
| `update_version/Lumen_Update_Version_10.md` | Adds this round's implementation, evidence, decisions and submission description. |

No existing source file, fixture or historical report was deleted. The legacy Gutendex implementation is inactive rather than erased.

## 5. Project benefits

The browser can now exercise the real recommendation graph, see progress and inspect reasons/channels instead of receiving only keyword matches. Metadata filters have enforceable boundaries. Sparse constrained searches retain real matches and explain their limited coverage. Clear language-course substitutions cannot be used simply to increase a literary result count. Optional source failures do not remove otherwise valid retailer-linked cards.

The evaluation gate now has actual HTTP first-book measurements and retained candidate/wire evidence. Earlier failures remain inspectable with their exact original suites. The approved scope revisions are explicit and separate from test outcomes.

## 6. Future impact and compatibility

- No database migration, table deletion or stored-format change occurred. Search/book/result persistence and the planned single-book endpoint remain later work.
- No new paid service, model provider, major bibliographic source, recurring cost or public deployment was added. Real verification used existing configured services and their normal usage.
- Existing keyword JSON clients remain compatible; recommendations require the SSE Accept header. New constrained requests must use SSE. The retired free-only true flag is deliberately rejected under the explicit approval.
- Source work keys are internal. Descriptions are work-level catalog evidence, not proof of ISBN-edition identity or independently verified author nationality.
- The course check and proper-word grounding check are heuristics. Passing them does not establish complete semantic relevance or factual correctness.
- Apple cache/rate coordination is process-local. Shared Redis coordination, the full result/source caches, IP hourly limiting and the daily model-call cap still need implementation before production exposure.
- Local HTTP evaluation is not a public-deployment latency guarantee, concurrency/load test or future source-uptime guarantee. Retailer destination uptime/stock is not proved by a valid search URL.
- Restoring free reading requires a reliable verified source and a new approved implementation/evaluation round. The old artifacts provide a reversible reference without enabling runtime access.
- Multi-worker deployment, persistence, cache policy and production release remain separate work; starting this local preview does not release or deploy the product publicly.

## 7. Verification

Observed checks so far:

- Backend: 262 tests passed; scoped Ruff checks passed. The last ten regressions include explicit topic concessions, allowed ordinary negation, and prevention of re-entry with a rewritten reason.
- Frontend: four stream-parser tests passed, ESLint passed, and the production build/type checks passed.
- Dependency lock: offline check resolved the existing 71 packages without changes.
- Gutendex: a real search probe raised ReadTimeout; no successful search is claimed.
- Historical suite hashes match their corresponding original captures before Git upload. Their exact bytes are preserved by `.gitattributes`. The archive whitespace rule recognizes their intentional CRLF terminators while retaining checks for actual trailing blanks, blank lines at EOF and spaces before tabs.
- The first two HTTP captures completed all 20 queries, each with one count failure; both gates correctly failed. All their other checks passed, with latency not applicable to nonsense cases. They are retained unchanged.
- The third complete HTTP capture passed under the approved scope: 123 cards, 52 logical model calls (maximum six per request), first-book receipt 3,417.22–9,185.36 ms, and all 42 captured source fingerprints matched. Subsequent browser review found an additional weak-match scenario; the reason check was strengthened and another complete run was required. The third report is preserved, not represented as validation of the later change.
- Fourth backend-only capture: `eval-http-20261108-round10-semantic-verified.json`, completed 2026-11-08 12:24:46–12:31:31 Europe/Madrid (CET). All 20 cases passed authenticity, language, count, links and reason; first-book latency passed for all 18 book-producing queries and is not applicable to the two nonsense cases. The gate returned PASS / process exit 0. It captured 109 cards and 64 logical model calls, never more than six per request. First-book receipt ranged from 3,588.83 to 11,419.17 ms. Twelve work-description lookups occurred across the suite, never more than eight per request; four admitted-mismatch ISBNs were excluded. All 42 source fingerprints matched at that revision. Optional Apple outcomes were 57 matched, 50 not found and two insufficient-metadata outcomes; none were unavailable. No retired-provider lookup was present. This capture predates the transport-header refinement and is not the final frontend timing evidence.
- Final frontend-path capture: `eval-frontend-20261108-round10-final.json`, 2026-11-08 12:49:49–12:57:09 Europe/Madrid (CET). The complete 20-case gate passed with process exit 0 through `http://127.0.0.1:3000`: authenticity, language, count, links and reason passed for all 20; first-book latency passed for all 18 book-producing cases and is not applicable to the two nonsense inputs. First-book receipt was 3,468.02–14,430.72 ms. First events arrived at 11.13–1,352.05 ms, including cold model-wrapper initialization. All 20 responses had no content encoding, confirming that gzip no longer held the stream.
- The final frontend capture retains 124 cards and 58 logical model calls, at most six per request; two explicitly admitted-mismatch ISBNs were excluded. Sixteen description lookups occurred across the suite, at most eight per request. Apple outcomes were 62 matched, 61 not found and one insufficient-metadata outcome. No optional lookup was unavailable. All 42 current application/evaluation fingerprints and the approved suite archive SHA-256 match the final capture. The source and retry/model-call limits were not bypassed.
- The native preview backend was restored after the evaluator closed its temporary backend. Both `/en` and `/es` returned 200; the frontend `/api/health` returned 200 with PostgreSQL and Redis healthy. The background services remain available on frontend port 3000 and backend port 8001.
- Final repository checks found no configured API keys or connection URLs in pending files, no added authorship credits, and no Chinese explanatory prose. Original Japanese author names in captured bibliography were identified by a Han-character scan and intentionally preserved as source data. Historical reports were not edited to remove or translate evidence.

Browser verification used the in-app browser. The separate Browser plugin was not available; existing computer/browser control provided the supported inspection and interaction APIs. The flow under test was `/en` or `/es` → choose language/filters → submit a request → inspect progress, cards, descriptions and limited/empty results.

| Browser check | Observed result |
| --- | --- |
| Page identity | `/en` and `/es` displayed the Lumen title and the corresponding locale. |
| Meaningful content | Search controls, source-backed cards and final status messages rendered. |
| Framework overlay | No framework error overlay was present. |
| Console | No relevant warning/error entries were returned from the checked tab. |
| Interactions | Language switching, nonsense empty-state handling, Spanish recommendations, description expansion and filter selection worked. |
| Limited-result scenario | The Toine Heijmans sea-novel request with 2010s/short filters returned `En el mar`, 2018, 128 pages, with the corrected singular Spanish notice and four actual channel buttons. |
| Responsive layout | Desktop and a 390×844 narrow viewport were inspected. Narrow content width equaled viewport content width (375 CSS pixels after its scrollbar), with no horizontal overflow. The temporary viewport override was reset. |
| Evidence/handoff | Full-page local review images were saved outside the repository; the verified preview tab was left visible for inspection. |

Local screenshots include `lumen-update-10-mobile.jpg`; they are review artifacts, not files prepared for GitHub upload. Browser inspection is not a production cross-browser or load test. The separate final 20-case frontend HTTP capture supplies actual forwarding-path timing evidence.

Restricted local runs initially failed on Windows filesystem/cache access for the Next.js build and the uv lock check. Repeating those same checks with normal filesystem access passed. A harmless native Node module-type warning appears during the test command; tests pass and the built application does not depend on TypeScript stripping. No check was disabled to obtain a pass.

Unit tests use offline responses/fixtures. The description fixture contains selected fields from an actual work response, not a simulated successful search. Focused graph/ASGI diagnostics were used while investigating constrained counts; their durations are not substituted for real HTTP first-book evidence. No new Docker image, migration, public deployment, retailer stock check or full production load test is claimed.

## 8. Approvals and remaining work

Explicit approvals in this round:

1. Retire unavailable Gutendex/free-only reading and adjust that evaluation scope, preserving historical failed reports.
2. Treat the two multi-constraint cases as niche, retaining all their constraints and allowing 1–4 books only after both retries, with an explicit limited-results notice.

The existing stack, real-candidate ISBN checks, fixed graph and maximum broadening/model-call budgets are unchanged. Routine implementation of the already specified HTTP streaming, card display and filters did not require a new architecture decision.

Next work: persistent book/search/result writes with the established foreign keys, the single-book endpoint, shared Redis caching/rate limits, daily-call protection, and production/deployment checks. Continue semantic inspection of constrained recommendations; do not interpret six heuristic checks as proof of every reader constraint.

## 9. GitHub submission

The user explicitly confirmed uploading this reviewed branch, merging it into main, and beginning the next round on 2026-11-08. The authorized scope includes the previously disclosed local Update 9 dependency. Implementation commit `cff3b7a87b0fad02bfebdd38cb173ae09b9477b4` was pushed to `origin/codex/update-10-search-preview`; main was fast-forwarded and pushed successfully. A subsequent remote-ref check confirmed both GitHub refs at that implementation commit before this documentation-only publication finalization. No pull request, release or public deployment was performed.

Proposed commit title:

`feat: stream filtered recommendations and retire unavailable free lookups`

Proposed commit description:

> The web interface previously returned keyword-only books and could not exercise the validated recommendation graph or its reading channels. Add an opt-in HTTP SSE path and bilingual client with progress, complete cards, enforced date/page filters and explicit limited-result feedback. Preserve keyword JSON compatibility and reject unsupported free-only true requests.
>
> Retire unavailable Gutendex lookups under the explicit scope approval. Improve constrained retrieval using verified catalog author seeds, bounded real Open Library work descriptions and conservative course/literature separation. Keep real-candidate ISBN validation, the 30-book ranking limit, two broadening retries and six logical model invocations.
>
> Evaluate all 20 cases over real loopback HTTP, retain failed captures and exact historical suites, and apply the separately approved niche classification for the two multi-constraint cases. Verification outcomes and limitations are recorded in update_version/Lumen_Update_Version_10.md. No dependency version or database schema changes; persistence, shared quotas/caches and production rollout remain future work.

> Validation: 262 backend tests and four frontend stream-parser tests passed; scoped lint, frontend production build/type checks, offline dependency-lock verification and browser interaction checks passed. The final 20-case evaluation through the actual frontend passed all six gate requirements, with 18 first-book timings of 3.47–14.43 seconds and latency not applicable to the two nonsense cases. Preserve the earlier failed frontend-buffering probe and the cold-start diagnostic. SSE uses no-transform to prevent gzip buffering, without disabling ordinary page compression.

The implementation commit uses the title and description above. This record documents confirmation received for Update 10; it does not authorize uploading later implementation rounds. The archive whitespace configuration was also checked with a negative example: intentional CRLF was accepted and actual trailing spaces were still rejected.
