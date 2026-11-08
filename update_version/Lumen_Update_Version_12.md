# Lumen Update Version 12

## 1. Basic information

- **Date:** 2026-11-08 (Europe/Madrid).
- **Branch:** `codex/update-12-cache-and-usage-guards`.
- **Baseline:** local Update 11 checkpoint `c2b6d927860ac8430f67eda56962eb4da8f1a501` on `codex/update-11-search-persistence`.
- **Published baseline:** `main` remains at `bc9abff8aa6b62e4dc3ee70f1d3ed3086eeb1d11` from Update 10. Update 11 is a dependency of this round and has not been uploaded or merged.
- **Objective:** implement the specified shared caches, hourly search limit and daily model-request safeguard while preserving validated recommendations and persistence.
- **Actual scope:** Redis cache/usage boundaries, guarded model transport, cached SSE replay, original catalog-fetch timestamps, bilingual limit messages, native/offline/live verification, deployment-entry-point configuration and English documentation.

The user asked to start the next round without authorizing a new upload. The completed Update 11 working tree was inspected and preserved in a local commit with the verified user author/committer identity before creating this branch. Its historical record remains unchanged; its previous statement that no commit existed describes the end of that earlier round. No unrelated edits were present when Update 12 began.

## 2. Technologies used

No dependency or external service was added.

- **Redis 7 and redis-py asyncio:** share expiring JSON caches and usage counters across API workers using the same logical database.
- **Redis Lua and server time:** check/increment counters atomically, so simultaneous requests cannot each claim the final available allowance. Server time supplies common UTC clock-hour/day buckets.
- **httpx transports:** cache raw successful catalog responses underneath the existing parsers, and charge actual outbound model HTTP attempts before sending them. Provider SDK retries pass through the same guarded transport.
- **Pydantic:** validate completed cached state/cards, structured parse output, proxy settings and internal aware fetch timestamps before reuse.
- **SHA-256:** derive opaque request keys and invalidate parse/result caches when application source, store rules or the configured model change.
- **Existing FastAPI, LangGraph and SQLAlchemy:** retain the fixed search graph and stream contract, enforce HTTP admission, and persist cache hits without refreshing books.
- **pytest, actual PostgreSQL/Redis and the existing HTTP evaluator:** test corruption, concurrency, failure paths, retry accounting, historical replay and real search behavior.

## 3. Implementation

### Shared optional caches

`JsonCache` stores bounded JSON values, with a maximum serialized size of 2,000,000 bytes. Cache read/write failures do not become authoritative empty catalog results. Invalid entries are ignored or removed; mandatory usage checks have a separate fail-closed path.

| Cache | Contents and key basis | TTL |
| --- | --- | --- |
| Parse | Validated initial structured query; actual constrained prompt and language, plus application/rules/model signature. | 7 days |
| Google Books | Successful raw catalog JSON keyed by the exact HTTPS URL/parameters. | 24 hours |
| Open Library | Successful search/work-description JSON keyed by the exact validated HTTPS URL/parameters. | 24 hours |
| Result | Complete validated state and final cards keyed by exact original request, language and normalized filters, plus application/rules/model signature. | 6 hours |

The version signature includes application Python source and `stores.yaml`; text is normalized for Git line-ending conversion. Raw catalog caches remain independent of model versions because parsers always process the stored provider payload again. Only the established Google Books volume endpoint, Open Library search and validated work-description paths are cached. Other requests, including Apple Books, use the existing behavior. HTTP errors and invalid JSON are not stored as successful responses. Apple Books retains its existing bounded process-local optional-lookup cache.

Initial parse hits skip the parsing model invocation and correctly record zero parsing calls. Ranking, candidate normalization, strict filters, validation, at most two broadenings and at most six logical model invocations remain unchanged on misses. Failed/incomplete searches never populate the result cache. Expected empty completed searches can be cached.

Completed result reads revalidate the request identity, complete pick/card snapshot, ISBNs, language, ranks, reasons, metadata filters, current channel rules, safe HTTPS hosts, formats and labels. Malformed or mismatched entries become misses. Result hits stream individual cards without a graph, model or retailer call, use a new search UUID, and save a new anonymous search/result history.

### Original source freshness and database behavior

Raw catalog cache entries retain their original fetch time. This time travels in an excluded internal `catalog_fetched_at` field on candidates and never appears in public cards or GET responses. Merging uses the oldest known contributing timestamp, including fetched work descriptions, rather than claiming newer evidence than is available.

Freshly processed searches pass this source timestamp to the existing book row. An older source-cache response cannot overwrite a newer stored snapshot. On a complete result hit, the repository verifies that the referenced books still exist with the expected language, then inserts only the new search and ordered results. It neither overwrites book metadata nor changes `fetched_at`. Existing foreign keys and all-or-nothing transaction behavior remain active.

No schema migration or incompatible public data-format change was introduced. Historical candidates without an internal timestamp retain the established save-time fallback. Automatic 30-day refresh remains unfinished; a timestamp is provenance, not a refresh scheduler.

### Hourly admission

Both SSE and legacy keyword JSON search routes enforce 20 admitted searches per client IP per UTC clock hour, including full result hits and searches that later fail. Invalid request bodies/unsupported legacy filters are rejected before admission. Rejected over-limit requests do not increase the counter. Limit responses are HTTP 429 with `rate_limited` and `Retry-After`.

IP identifiers appear only in Redis usage keys. They expire at the end of the clock-hour bucket, never later than one hour after creation, and are not copied into PostgreSQL, result snapshots or public responses. This is the specified clock-hour policy, not a rolling 60-minute window.

Uvicorn now runs with `--no-proxy-headers` in the backend Docker entry point and HTTP evaluator, so the application's identity boundary sees the real socket peer. `TRUSTED_PROXY_IPS` is an explicit JSON list of controlled proxy IPs/CIDRs; its default is empty, and catch-all networks are rejected. Untrusted forwarding headers are ignored. A trusted chain is validated and walked from the nearest hop back to the first untrusted address. Malformed or overlong chains fall back to the socket peer. The local preview consequently shares its proxy peer's allowance unless a controlled, correctly configured proxy supplies the client chain. Production proxy routing/header sanitation still needs verification.

### Daily actual-request cap

The user explicitly selected **100 actual AI requests per day, including failed retries**. `DAILY_AI_CALL_CAP` defaults to 100 and accepts only positive integers. The counter is shared across API workers using the same Redis database and resets at the UTC day boundary.

Uncached SSE admission checks whether any allowance remains. Before each actual outbound model HTTP attempt, including each provider SDK retry, `BudgetTransport` atomically consumes one allowance. Concurrent searches may pass the preliminary check together, but the per-attempt check prevents them from exceeding the shared cap. Charges occur before sending and are not refunded for failed or uncertain attempts. The existing SDK retry policy is retained; denied attempts never reach the underlying network transport.

A full result hit remains available after the daily cap is exhausted, subject to the hourly search limit. An uncached request gets a sanitized HTTP 503 maintenance response with `rate_limited` and `Retry-After`. Exhaustion during an active stream emits a sanitized `rate_limited` error followed by termination, without persisting or caching an incomplete search. SDK-wrapped usage denials retain their meaning instead of becoming generic model failures.

If Redis usage checks are unavailable, new search work fails closed with a sanitized 503 or stream error. Keys, connection strings and exception text are not sent to readers. GET book details and health checks do not consume search/AI allowance.

### Reader-facing limit messages

The existing page previously displayed every failed HTTP search as a generic failure. It now distinguishes hourly 429 responses from daily-cap 503 responses and uses localized English/Spanish messages in the existing accessible alert. Midstream daily denials use the same daily message. Unknown codes, malformed bodies and unrelated failures retain the generic message; raw server exception messages are never rendered. Submission cleanup and cancellation protection remain in the existing event handler, without adding effects, dependencies or a redesign.

## 4. File changes

| File | Before/after purpose |
| --- | --- |
| `backend/app/usage.py` | Added atomic shared counters, proxy identity handling, typed denials and the actual model-request transport boundary. |
| `backend/app/search_cache.py` | Added versioned request keys, complete snapshot storage and defensive cached-result reads. |
| `backend/app/catalog_cache.py` | Added successful raw catalog-response caching with original fetch timestamps. |
| `backend/app/cache.py` | Expanded health-only Redis setup into bounded optional JSON cache operations and finite connection/read timeouts. |
| `backend/app/config.py` | Added the approved positive daily cap and explicit validated trusted-proxy list. |
| `backend/app/http_client.py` | Optionally wraps the shared catalog transport without changing existing standalone/test callers. |
| `backend/app/llm.py` | Supplies the guarded async HTTP client to the existing model wrapper and preserves nested usage denials. |
| `backend/app/main.py` | Creates and closes shared cache/usage/model-HTTP resources in the existing lifespan. |
| `backend/app/api/search.py` | Adds mandatory admission, cache lookup, daily preflight and sanitized HTTP denials for both search paths. |
| `backend/app/search_stream.py` | Adds per-card cached replay, fresh search persistence without book refresh, result-cache writes after completion and midstream usage errors. |
| `backend/app/graph/workflow.py` | Adds optional initial parse reuse with accurate model-call accounting; graph topology, prompts and bounded retries are unchanged. |
| `backend/app/repository.py` | Exposes complete-snapshot validation, preserves real source-fetch timestamps/newer rows, and saves cache-hit history without refreshing books. |
| `backend/app/sources/schemas.py` | Adds an excluded aware timestamp for internal provenance; public serialization is unchanged. |
| `backend/app/sources/google_books.py` | Propagates source-fetch timestamps from transport metadata into normalized candidates. |
| `backend/app/sources/open_library.py` | Propagates source-fetch timestamps without changing edition/language normalization. |
| `backend/app/sources/merge.py` | Retains the oldest known contributing timestamp while preserving the established primary-source merge rules. |
| `backend/app/sources/descriptions.py` | Includes work-description provenance in the conservative merged fetch timestamp. |
| `backend/Dockerfile` | Disables server-level forwarding-header rewriting so explicit application proxy trust controls identity. |
| `.env.example` | Documents the approved 100-attempt cap and explicit proxy-list configuration without secrets. |
| `backend/evals/http_run.py` | Uses the same raw-peer boundary and records active daily cap/UTC day policy in live reports. |
| `backend/evals/README.md` | Documents active evaluation safeguards, isolated cold-cache testing and the boundary of graph-only diagnostics. |
| `backend/tests/usage_fixtures.py` | Adds explicit offline usage/cache replacements for route tests. |
| `backend/tests/test_usage.py` | Tests proxy chains, settings, fail-closed checks, transport denial and preservation of SDK-wrapped errors. |
| `backend/tests/test_search_cache.py` | Tests cache isolation/corruption, no-call replay, TTLs, parsing reuse and source timestamp preservation. |
| `backend/tests/test_usage_api.py` | Tests both response modes' admission failures, spoofed identities and midstream denials without persistence. |
| `backend/tests/test_search_api.py` | Supplies explicit offline usage dependencies while retaining existing legacy API checks. |
| `backend/tests/test_search_stream.py` | Supplies explicit offline admission dependencies for the existing HTTP stream checks. |
| `backend/integration_tests/conftest.py` | Adds isolated disposable Redis key namespaces alongside the existing disposable PostgreSQL schemas. |
| `backend/integration_tests/test_cache_usage.py` | Adds real Redis concurrency/TTL/cache checks, actual SDK retry accounting with mocked external HTTP, native freshness and cap-exhausted cache-hit persistence. |
| `backend/integration_tests/test_replay_and_stream.py` | Updates explicit application test dependencies while preserving all 20 recorded-case persistence checks. |
| `README.md` | Documents caches, limits, proxy setup, provenance and the remaining production boundary. |
| `frontend/lib/search-error.ts` | Adds a typed mapping from known HTTP status/code pairs to local message keys without displaying raw response text. |
| `frontend/app/[locale]/page.tsx` | Handles expected hourly/daily denials explicitly and retains the existing accessible alert and cancellation behavior. |
| `frontend/messages/en.json` | Adds English hourly/daily limit messages and recovery guidance. |
| `frontend/messages/es.json` | Adds intentional Spanish translations for the same states. |
| `frontend/tests/search-error.test.mjs` | Tests distinct hourly/daily messages and safe generic handling of malformed/unrelated errors. |
| `update_version/Lumen_Update_Version_12.md` | Adds this round's detailed record and proposed submission. |

Five new JSON evidence files are listed in section 7. No existing source files or historical reports were deleted or overwritten. Database models, migrations, lockfiles, provider choices, ranking prompts and frontend proxy configuration remain unchanged.

## 5. Project benefits

Repeated requests can avoid paid model work and repeated catalog requests across backend processes. Complete hits remain useful when the daily AI allowance is exhausted. Atomic counters prevent concurrent workers from over-claiming a shared allowance, and the transport-level boundary includes provider retries that logical graph-call counts alone would miss.

Request identity and language/filter separation prevent an unrelated cached search from supplying recommendations. Source timestamps and nonrefreshing result hits preserve the meaning of book freshness. Separate search/result history is retained even when expensive computation is reused.

The implementation uses the existing stack and keeps optional cache failures separate from mandatory spending/admission checks. This makes outages explicit without treating failed providers as empty catalogs.

## 6. Future impact and limitations

- **API compatibility:** successful request/card/done formats and the legacy keyword JSON response are unchanged. Search routes now intentionally return 429/503 when a configured safeguard denies work. Existing SSE buffering headers remain intact.
- **Database:** no migration. New cache-hit histories increase search/result rows while leaving books unchanged. Cached source snapshots cannot overwrite newer book rows.
- **Operations:** all API workers must use the same Redis logical database and cap configuration for one shared allowance. Test databases have independent counters and must be identified as test isolation, not used to bypass an active production denial.
- **Proxy trust:** direct peers are the safe default. A public deployment requires a controlled proxy that supplies a trustworthy chain and cannot be bypassed by untrusted peers in a trusted network. This round does not establish a public multi-user proxy deployment.
- **Budget meaning:** the counter bounds attempted model HTTP requests, not token counts or a fixed currency amount. Standalone diagnostic model scripts are outside the HTTP API guard. Redis data loss loses counters as well as caches; durable budget accounting across a Redis reset requires further design before launch. A backend process restart alone retains Redis counters/cache entries.
- **Cold concurrency:** simultaneous identical misses can still duplicate model/catalog work within the enforced limits; distributed request coalescing is not implemented.
- **Remaining features:** automatic 30-day refresh, full original provider-payload/debug storage, unselected-candidate caching, a frontend detail/share page, durable production budget operations and deployment checks remain unfinished.
- **Observed relevance gap:** a manual request explicitly naming an author returned additional authors. The current lexical checks and fixed evaluation do not establish complete author matching. This remains an unresolved correctness issue; caching a snapshot does not improve its semantic relevance. The failed manual observation is retained and should drive the next regression case and author-constraint fix.

## 7. Verification

- `python -m pytest -q`: **302 passed**, final run 5.04 seconds; no live network in the unit suite.
- `python -m pytest -q integration_tests`: **28 passed**, final run 9.08 seconds; real local PostgreSQL/Redis, isolated schemas/keys. The provider SDK retry tests use recorded mock HTTP responses, not paid live provider calls.
- Ruff lint passed; `ruff format --check app scripts tests evals integration_tests` accepted all 84 Python files.
- Native concurrency: two guards share exactly 20 accepted admissions out of 35 simultaneous same-IP attempts; a second IP has its own allowance. A five-attempt shared daily budget allows exactly five out of fifteen concurrent attempts. TTLs and old-day separation are checked.
- Native retry accounting: two mocked 500 responses followed by success consume three actual transport attempts. With a one-attempt cap, only the first request reaches the underlying transport and the later SDK retries are denied.
- Native persistence: complete result hits work at an exhausted daily cap, create a second search history and leave the book timestamp unchanged. Older source snapshots cannot replace a newer book. Existing rollback/foreign-key/concurrency/cancellation and 20-case recorded persistence checks remain passing.
- Two initial integration failures were test-harness defects: an asynchronous TTL assertion and a missing optional-cache write method on an offline double. Both were corrected; no product check was removed or bypassed. One earlier test cache key outside its intended test prefix was identified by its exact fixture payload and removed; zero disposable test keys remained afterwards.

### Complete live evaluation

`backend/evals/results/eval-frontend-20261108-round12-cold.json` records a new complete **20-case frontend HTTP SSE gate: PASS**. All 20 cases passed authenticity, language, count, link rules and the reason heuristic. First-book latency passed for all 18 nonempty cases; the two nonsense cases correctly have no applicable first-book timing. The run returned **121 cards**, used **54 logical and actual model HTTP requests**, and measured **3,712.48–10,143.15 ms** to the first book. Neither the 15-second limit nor any other evaluation criterion was relaxed.

`backend/evals/results/eval-environment-20261108-round12.json` retains the gate report's SHA-256, source/rule cache signature, active cap and actual Redis counters. The evaluation used dedicated local Redis logical database **15**, verified empty before the run, with the same **100-attempt daily cap and 20-search hourly limit enabled**. It finished with exactly 54 AI attempts and 20 admitted searches. This isolates evaluation keys/allowance from the interactive preview; it does not disable admission or increase a limit. Raw catalog reuse within the initially cold run remains permitted by the specified cache policy. This was a new live run, distinct from the historical recorded-case native-database replay.

### Restart, cache accounting and a failed manual semantic check

`backend/evals/results/cache-restart-20261108-round12-baseline.json` records a separate real UI search and its immediate repeated query in the normal interactive Redis database. The request was `Quiero una novela sobre el mar de Toine Heijmans`, with 2010s/short filters. It produced three saved books and six model attempts. **The exact-author semantic check failed:** only one book was by Toine Heijmans; the others were by Herman Melville and Hugo Hiriart. The snapshot records the authors and explicitly marks this check false. This is not counted as a successful author-constrained recommendation or hidden behind the passing fixed gate.

After restarting the backend process, `backend/evals/results/cache-restart-20261108-round12.json` records a real repeated POST through the frontend. The same three cached cards streamed in order with **65.51 ms** to the first book and **81.61 ms** total. The API created a new search UUID and ordered SQL results; all three detail GETs succeeded; every book timestamp remained unchanged. The interactive AI counter stayed at **6 before and 6 after**. The report sets `implementation_checks_passed: true`, `all_manual_checks_passed: false`, retains the author failure and links the baseline by SHA-256. Cache correctness/persistence passed; author relevance did not. The two live environments together consumed 60 actual provider attempts during these checks, below the approved initial 100-attempt allowance; mocked SDK tests made no paid provider requests.

`backend/evals/results/eval-budget-reconciliation-20261108-round12.json` records the subsequent one-time accounting of the evaluation's 54 actual attempts into the normal shared counter. An atomic Redis operation increased the interactive daily count from **6 to 60**, without sending model requests or changing hourly counters. An expiring receipt keyed by the evaluation-environment report's SHA-256 prevents duplicate reconciliation. The normal preview therefore has **40 attempts remaining** in the approved 100-attempt UTC-day allowance at this point; test isolation does not create an extra spending allowance. The restart report's earlier unchanged count of six describes the cache request before this accounting step.

Observed public tables after the restart check contained 144 books, 30 searches and 153 results. These are the current local preview totals, not a claim that every row was created in this round. Public records were not deleted or reset. Disposable native-test schemas and Redis key namespaces were cleaned separately.

### Frontend verification

- `npm test`: **6 passed**, including the existing stream parser and new denial mapping cases. Node retained its existing module-type warning; it did not fail the tests.
- `npm run lint`: passed.
- `npm run build`: passed compilation, TypeScript and static generation on Next.js 16.4.2. The frontend was restarted with this build.
- Rendered flow checked: Spanish page -> constrained search -> streamed cards/limited-results notice -> repeat search -> English language switch. Both routes had title `Lumen`, meaningful content, enabled controls after completion, no framework overlay and no captured console warnings/errors. The existing constrained metadata filters and bilingual navigation remained functional.
- The standalone Browser plugin was unavailable. Regular Playwright module initialization failed with a missing default export; no dependency was installed. The available in-app computer/browser controls completed the rendered checks instead. A screenshot of the final English page was saved outside the repository and the preview tab left open.
- Actual hourly/daily denial alerts were covered by API/mapping tests rather than forced in the live browser. No production proxy, mobile viewport, load, automatic 30-day refresh or durable Redis-reset recovery test was performed. The passing checks do not establish production readiness or complete semantic relevance.

### Final scope and integrity checks

- All **47** application/evaluation source fingerprints in both the cold live gate and restart report match the final backend source. The frontend message changes were built and checked separately after the live gate; frontend proxy routing was unchanged.
- Final Ruff lint/format checks and `git diff --check` passed. All **42** changed/new files were reviewed for trailing whitespace, repository language, configured credentials and unwanted attribution. The only Han characters were retained original bibliographic names/titles in the live catalog capture; no Chinese explanatory project content was added. The credential scan's initial match was the intentionally public, unauthenticated localhost Redis URL in `.env.example`, not a credential leak.
- Final direct backend health, frontend-forwarded health and both `/en` and `/es` pages returned 200. PostgreSQL and Redis were healthy. Zero temporary `lumen_test_*` schemas and zero disposable `lumen:test:*` keys remained.
- The branch remains `codex/update-12-cache-and-usage-guards`, with the verified user-authored Update 11 checkpoint as its baseline. Local `main` remains at the published Update 10 commit; no Update 12 upload or merge occurred.

## 8. Approvals and remaining work

The user authorized this implementation round and explicitly approved an initial daily limit of **100 actual requests including retries**. No new architecture, provider, dependency, paid service, schema, capability removal or production release was introduced. The fixed graph, real-book validation, existing foreign keys and previous free-only/niche approvals remain in force.

Remaining work is described in section 6. Exact-author matching and an explicit author regression scenario should be addressed before treating author-constrained queries as reliable. No additional approval was inferred for uploading either this round or its Update 11 dependency. Major production persistence/proxy/budget decisions will need a concrete proposal if they materially change the current constraints.

## 9. GitHub submission

**Proposed commit title**

`feat: cache validated searches and enforce shared usage limits`

**Proposed commit description**

Repeated searches previously repeated model/catalog work, and the API lacked the specified hourly and daily safeguards. Add shared bounded Redis parse/catalog/result caches, atomic 20-per-IP clock-hour admission and the approved 100-attempt UTC-day model cap, including provider retries.

Replay complete validated snapshots one card at a time, persist a new anonymous search history and preserve original catalog timestamps. Keep the existing stack, schema, successful API formats, fixed graph and validation constraints. Add explicit proxy trust, sanitized denial paths and fail-closed usage checks; cache operations remain optional. Document the remaining Redis-reset durability, standalone-diagnostic and production-proxy boundaries.

Validation: 302 offline tests, 28 native Redis/PostgreSQL tests, six frontend tests, lint and the production frontend build passed. A new cold-cache 20-query frontend gate passed all six checks, returning 121 cards with 54 actual model requests; first books arrived in 3.71-10.14 seconds. A restart check returned cached cards in 65.51 ms with no new AI calls, preserved book timestamps and saved new search history. A separate manual exact-author check failed and remains explicitly recorded for follow-up; these passing infrastructure checks do not prove full semantic accuracy.

See `update_version/Lumen_Update_Version_12.md` for technologies, file scope, retained reports, verification limits, compatibility and future impacts.

**Actual status at submission preparation:** The user explicitly authorized uploading and merging this round, including its disclosed Update 11 dependency, before starting the author-constraint repair. Update 11 is the local baseline above, and Update 12 is being prepared for the authorized commit, branch push and fast-forward merge into `main`. Publication is not yet claimed in this record; the following round's record will retain the verified resulting commit and remote state. No pull request, release or production deployment was authorized or performed.
