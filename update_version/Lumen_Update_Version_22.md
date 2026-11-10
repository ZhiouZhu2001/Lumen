# Lumen Update Version 22

## 1. Basic information

- **Round:** 22, an implementation round rather than an application release.
- **Date:** 2026-11-10, Europe/Madrid.
- **Branch:** `codex/update-22-search-experience`.
- **Known baseline:** clean local `main` at `a8c9deaa56f674474d4927f36bbd519139fa1c4d`, matching its known `origin/main` tracking reference. Rounds 20 and 21 were already merged; there is no pending implementation dependency.
- **Objective:** complete the planned frontend round covering language preferences, search state, loading feedback and mobile behavior.
- **Actual scope:** frontend state factories, safe language persistence, runtime-checked search events, cancellation, responsive and accessible controls, shared book validation, frontend tests and the container build allowlist. No backend application, prompt, retrieval, migration, API wire format or spending policy changes.
- **Working tree:** inspected before implementation; no existing user changes were present. The new branch was created before source edits. This record is the next unused number after 21.

## 2. Technologies used

- **Zustand 5.1.0:** added and locked exactly, implementing the state-management technology already selected in the project specification. Vanilla store factories isolate mounted search pages and server-rendering requests; `persist` stores only the coupled book/interface language.
- **React 19.3 and Next.js 16.4.2:** existing hooks, client providers and App Router navigation support interactive state. `useId` gives cached locale-page instances distinct form identifiers. No shared mutable store is created at module scope.
- **next-intl:** retains English/Spanish messages, locale URLs and existing cookie-based root-language negotiation.
- **Fetch, AbortController and ReadableStream:** retain the existing POST/SSE flow while preventing superseded or cancelled requests from updating active results.
- **TypeScript and Node's native test runner:** check the client event contract and exercise real asynchronous state transitions with local response fixtures. `allowImportingTsExtensions` enables explicit `.ts` runtime imports used by native tests; strict checking and `noEmit` remain enabled.
- **Tailwind CSS:** retains the current visual style, adds responsive controls and loading placeholders, and respects reduced-motion preferences.
- **Playwright/Chromium and Docker Compose:** verify rendered production pages and the existing disposable five-service stack. Browser tooling and evidence are outside the repository; Playwright is not an application dependency.

No primary framework, model provider, bibliographic source or external service was replaced.

## 3. Implementation

### Search session and event contract

`createSearchSession` owns a Zustand store and one active request controller. The page supplies the locale and form actions through `useBookSearch`; it no longer implements fetch, stream parsing and result transitions inline. Form fields remain in memory and selected nonempty filters are sent using the existing request shape.

Every new search aborts the preceding controller. Response handling also checks controller identity, so even a test transport that ignores abort cannot replace a newer result. Cancellation and route/locale cleanup abort the request and clear provisional results. Cancelling retains the form so the reader can adjust it. Client cancellation does not promise server-side task recovery, reverse already-completed work or refund model reservations.

Known SSE events are decoded into a discriminated client type. Book metadata, ISBN checksum, rank, reason and link shape are checked before rendering. Unknown event names are ignored for additive compatibility; malformed known events fail safely. Books must arrive in consecutive rank order; repeated frames with the same ISBN/rank do not duplicate a card. A terminal event must agree with the number of distinct cards and its limited-results flag. Events after completion and streams ending without completion are rejected.

Cards remain provisional during streaming. Details links become available after a valid terminal response and stream completion. Errors, cancellation or inconsistent streams discard provisional cards. Error text comes only from known localized message keys, including separate hourly and daily-limit messages; raw server exception text is never displayed.

### Language preferences and privacy

`PreferencesProvider` creates a store per mounted provider, using the locale that produced the server HTML. Persistence hydrates only after mount. An explicit `/en` or `/es` URL determines the current language and updates the saved preference; an old preference never redirects a shared locale URL. Existing next-intl cookies continue to determine the root route.

The versioned `lumen:preferences:v1` entry contains only `{state: {language}, version: 1}`. Interface and book languages remain coupled as specified. Search text, filters, results and recommendation reasons are not persisted. Unknown preference versions, malformed JSON and unsupported languages fall back to the route language. Stored fields cannot replace store actions. Denied access and quota errors do not stop language selection or searching; persistence naturally cannot survive a reload when browser storage is unavailable.

### Loading, mobile and accessible controls

Loading displays two decorative card placeholders and one live progress region, including candidate counts when available. A visible cancel button provides an escape from a pending request. Form controls are disabled while that request runs. Placeholders stop animating under reduced-motion preferences.

The header and search controls stack on narrow screens, control targets retain a minimum 44 CSS-pixel height, and book covers use less width on phones. Page-count units move into the filter label so option text fits the desktop columns. Explicit labels, unique instance identifiers and described-by references avoid mixing English and Spanish labels when Next.js retains an inactive page in its navigation cache. Keyboard focus remains visible.

### Shared validation and packaging

Stored details and streamed cards now use the same metadata validator. Detail-specific identity, language, source and timestamp checks remain in the details loader, and its existing public helper import remains compatible. These client checks supplement the unchanged backend real-candidate validation and database constraints; they do not establish complete semantic recommendation accuracy.

The frontend Docker allowlist includes `stores/`, ensuring the new modules enter clean image builds. Secrets, local generated output and tests remain outside that build context.

## 4. File changes

| File | Change and before/after behavior |
| --- | --- |
| `frontend/.dockerignore` | Modified: allow `stores/` as a build input; previously the new directory would have been excluded. |
| `frontend/app/[locale]/layout.tsx` | Modified: provide per-instance language preferences beneath the existing translation provider. |
| `frontend/app/[locale]/page.tsx` | Modified: replace inline request/state handling with the search session; add cancellation, loading UI, unique form IDs, explicit labels, responsive controls and latest-intent locale navigation. |
| `frontend/components/BookDisplay.tsx` | Modified: reduce phone cover width and improve bounded, keyboard-focusable channel links on both book surfaces. |
| `frontend/components/BookCardSkeleton.tsx` | Added: decorative, reduced-motion-aware loading card. |
| `frontend/components/PreferencesProvider.tsx` | Added: isolate store creation, post-mount hydration and explicit-locale synchronization. |
| `frontend/lib/book-details.ts` | Modified: reuse common metadata validation while retaining detail-specific checks and ISBN helper compatibility. |
| `frontend/lib/book-schema.ts` | Added: common ISBN and public metadata runtime checks, replacing duplicated details-only logic. |
| `frontend/lib/search-events.ts` | Added: validate known SSE event payloads before applying them to client state. |
| `frontend/lib/use-book-search.ts` | Added: bind one search session to React and reset active results on locale/route cleanup. |
| `frontend/stores/preferences-store.ts` | Added: versioned, language-only persistence with validated hydration and safe storage access. |
| `frontend/stores/search-store.ts` | Added: isolated form/result state, request lifecycle, stale-response protection and completion checks. |
| `frontend/messages/en.json` | Modified: English language/results labels, cancel feedback and compact page-count choices. |
| `frontend/messages/es.json` | Modified: corresponding intentional Spanish localization. |
| `frontend/package.json` | Modified: add the specification's Zustand dependency pinned to 5.1.0. |
| `frontend/package-lock.json` | Modified: lock the dependency and its integrity metadata. |
| `frontend/tsconfig.json` | Modified: allow explicit TypeScript import extensions for native tests without relaxing strict checking. |
| `frontend/tests/preferences.test.mjs` | Added: hydration, minimal persistence, corrupt/future values, storage failures and independent stores. |
| `frontend/tests/search-session.test.mjs` | Added: request shape, asynchronous races, cancellation, errors, limited results and invalid streams. |
| `update_version/Lumen_Update_Version_22.md` | Added: this implementation, verification and submission record. |

No files were deleted. The submission scope is 20 files, including this record.

## 5. Project benefits

The page now presents search state instead of coordinating network internals. Request races and cancellation are independently testable. Shared runtime checks reduce disagreement between details and streamed cards, while explicit completion prevents an interrupted result from appearing saved. Language persistence satisfies the selected frontend approach without creating a local search-history archive. Responsive controls and uniquely linked labels improve the same flow for small screens and cached bilingual navigation.

## 6. Future impact and compatibility

- The three public endpoints, SSE payloads, database schema, bibliography providers, fixed graph, two-retry rule and daily cap remain unchanged. No migration or backend rollout ordering is required for the current contract.
- Frontend installation now includes Zustand; clean installs and container builds use the updated lockfile. No recurring paid service or new operating cost is introduced.
- Search results remain in memory. Accounts, favorites, historical personalization and durable background tasks are not added by these stores.
- The client event decoder is explicit and runtime checked, but it is not generated from Python/OpenAPI. Future event changes must still keep both sides consistent.
- Backend graph/repository/cache coupling and complete structured operational logging remain separate follow-up work from the architecture analysis. This round does not claim to resolve those concerns.
- Existing Next.js cookie negotiation and explicit localized book links remain compatible. Language storage is an additional browser preference; disabling it leaves the URL and cookie behavior available.

## 7. Verification

| Check actually performed | Result |
| --- | --- |
| `npm test` | **21 passed**, including all 11 existing tests and 10 new tests. New cases cover independent stores, minimal persistence, bad/future preferences, storage failures, request payloads, competing responses, cancellation, late HTTP errors, localized error selection, limited results and malformed/inconsistent streams. |
| `npm run lint` | Passed. |
| `npm run build` | Passed, including strict TypeScript checking and English/Spanish page generation. Explicit import-extension and schema-narrowing errors from the first type-check attempt were corrected before the successful checks; strict checking was not disabled. |
| Production-page browser verification | **15 checks passed** through regular Playwright with existing Chromium. Browser plugin not available. The native production page used `http://127.0.0.1:3022` and an isolated HTTP/SSE fixture backend on loopback port 8022. |
| Five-service container verification | Passed against the final source using the existing `check_container_stack.py` with Python UTF-8 mode. Both production images built; all five services became healthy; localized pages/assets/API routing, runtime exclusions, proxy identity, hourly denial and durable-budget protections passed. |
| Synthetic long SSE | Passed through the disposable Caddy stack: `status` at **22.55 ms**, terminal `done` at **65,018.54 ms**. This measures transport forwarding, not real first-book latency. |
| Cleanup | Owned disposable container resources, browser contexts, fixture HTTP server and this round's native frontend server were closed/removed. Unrelated containers were not operated on. |
| Scope and content checks | `git diff --check` passed. The 19 changed implementation/test/configuration files and the English update record were checked for scope, language and unwanted attribution; a source scan found no Chinese explanatory text or model-key patterns. |

The browser interaction loop exercised form filters -> loading placeholders -> a provisional card without a details link -> valid completion with five details links -> stored book details -> back navigation. Separate scenarios covered inconsistent completion, cancellation and late response, locale changes during a search, reload/root-language behavior, explicit locale precedence and a delayed competing locale navigation where the latest choice must win. Hourly denial, daily exhaustion, empty results, malformed cards and limited results all produced their expected localized feedback.

Desktop evidence uses 1280 x 900. Responsive checks include 320 x 740, 375 x 812, 768 x 1024 and landscape 812 x 375, plus 200% text scaling and reduced motion. The final pages had no blank screen, framework overlay, hydration exception or unexpected browser-console failure. The two expected console entries were HTTP 429 and 503 from deliberate denial fixtures. Final desktop and mobile screenshots were visually inspected. Compact length choices avoid the option clipping seen during screenshot review.

### Failures and corrections retained

The first container invocation used Windows' default CP1252 subprocess decoding and failed while reading Docker output (`UnicodeDecodeError`, followed by a missing captured-output error). Its owned resources were removed and its failed receipt is retained as `container-check.json`. Repeating the same checker with `python -X utf8` passed; a final repetition after the last source correction also passed. No check was removed or relaxed to obtain that result.

Early browser harness selectors also encountered the framework route announcer and inactive cached pages. Selectors were scoped to active/visible content. Investigation exposed the genuine duplicate fixed-ID label issue, which was corrected with per-instance IDs and explicit filter labels. The final suite verifies the accessible English query name after locale changes. A malformed array-valued status was additionally rejected without coercion and added to the invalid-stream test matrix. Node's existing nonfatal module-type inference warning remains in native test output; package module semantics were not changed solely to hide it.

### Retained local evidence

Logs, the temporary browser script, JSON receipts, screenshots and source fingerprints are retained outside Git at:

`C:/Users/zhu24/.codex/visualizations/2026/11/09/01a1c231-eace-76d1-a94d-ef3b305d67be/round22-tools/`

- `unit.log`, `lint.log`, `build.log`: successful final frontend checks.
- `qa.mjs`, `qa-results.json`: browser scenarios, 15 successful checks, fixture requests and console findings.
- `before-mobile.png`, `after-mobile-loading.png`, `after-mobile-results.png`, `after-desktop-results.png`: inspected layout/state evidence. Books shown in result screenshots are explicitly synthetic catalog fixtures.
- `container-check.json`: retained first encoding failure; `container-check-utf8.json`: successful retry; `container-check-final.json`: successful final-source container run.
- `verification-manifest.json`: LF-normalized SHA-256 fingerprints for all 19 changed implementation/test/configuration files, plus evidence-file hashes. Its SHA-256 is `d637807a888d1b81b18bde7b5ca8d5b3d19121a6e4c918a1776033c130230f94`.

The temporary browser tooling and evidence are not included in the branch. Persistent frontend tests remain in `frontend/tests/` and are picked up by the unchanged CI test command.

### Verification limits

No real model or catalog request was made. The 20-query live recommendation gate, real 15-second first-book requirement, production DNS/TLS, capacity and off-host recovery were not tested by synthetic fixtures. No Firefox/Safari or physical-device test was run. The separate backend unit/integration suites were not repeated because backend application source, prompts, retrieval and migrations did not change; the real disposable five-service integration checker was run. GitHub-hosted checks await an explicitly confirmed upload.

## 8. Approvals and remaining work

The user requested the next implementation round after architecture analysis. This implements the already selected MVP frontend technologies and behavior. No major architecture, capability, source, schema, privacy relaxation or spending decision was introduced, and no additional major-decision approval was required.

The next planned work is operational readiness: finish structured logging and prepare concrete production host/TLS/backup choices, then perform the final live bilingual quality and first-book-latency gate. Actual deployment, new costs and production backup/retention choices require their corresponding approval. This round makes no production-readiness or live recommendation-quality claim.

## 9. GitHub submission

**Proposed commit title**

`feat: complete persistent language preferences and search interactions`

**Proposed commit description**

Lumen kept search request handling inside the homepage and did not implement the specified browser language store. Extract isolated Zustand search sessions and language-only preferences, preserving explicit locale URLs and excluding queries and recommendations from persistent storage.

Add cancellation and stale-response protection, runtime-checked SSE/card payloads, terminal-result consistency checks and shared book metadata validation. Improve loading feedback, reduced-motion behavior, keyboard labels and mobile layout. Use unique form IDs across cached locale pages and package the new state directory in frontend images.

Validation: all 21 frontend tests, lint and the production build with TypeScript checks passed. Fifteen Chromium browser checks passed against isolated HTTP/SSE fixtures, including bilingual persistence, competing requests, cancellation, errors, keyboard controls and responsive/reduced-motion states. The final disposable five-service container check passed, including production image builds and a synthetic 65-second SSE. Retain the first Windows output-encoding failure and the successful UTF-8 receipts. No real model/catalog request, hosted CI run or public deployment was performed.

Preserve the public API, database schema, catalog/model providers, fixed graph and all spending safeguards. Add only the already selected Zustand dependency. Live recommendation quality and production deployment remain separate follow-up work.

See `update_version/Lumen_Update_Version_22.md` for the implementation, compatibility, evidence and follow-up work.

**Actual status:** local implementation on `codex/update-22-search-experience`, uncommitted and not pushed. No round-22 upload confirmation, pull request, merge, release or deployment has occurred. The reviewed round requires explicit upload confirmation before pushing; author and committer identities must be reverified before committing. No co-author or tool attribution has been added.

### Submission and main-merge authorization, 2026-11-10, Europe/Madrid

The user subsequently requested merging into `main` and starting the next round. This authorizes uploading the reviewed round-22 scope and its main merge. All 19 implementation/test/configuration fingerprints still match the reviewed verification manifest. The author and committer were reverified as `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`, and fetched remote `main` still matches the baseline above. The preceding local-only status describes the earlier checkpoint. Hosted results and the actual merge checkpoint will be recorded after verification; no pull request, release, deployment or paid service is included in this authorization.

### Automatic upload-review result

The functional scope was committed as `9cda2844c50cb5a973331c1258fc62c28b867b66`. Automatic approval review rejected the branch-push request: it interpreted the main-merge instruction as insufficient separate confirmation of this round's branch upload under the repository rules. The preceding authorization paragraph records the attempted interpretation; the rejection controls the pending external action. No push occurred. Explicit confirmation of the round-22 upload and remote-main synchronization was requested; local main integration and the next local round can proceed independently.

### Explicit upload confirmation

The user answered the upload question by explicitly confirming the round-22 branch upload and subsequent remote-main synchronization. This resolves the automatic review's missing-confirmation condition for this reviewed scope. Local `main` has already been fast-forwarded to the functional commit and its approval-status receipt; the next-round branch was created without implementation changes. The branch's hosted checks will be inspected before updating remote `main`. Round 23 remains a separate local scope requiring its own later upload confirmation.
