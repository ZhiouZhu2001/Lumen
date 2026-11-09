# Lumen Update Version 14

## 1. Basic information

- **Number:** 14, an implementation round rather than a release version.
- **Date:** 2026-11-09 (Europe/Madrid).
- **Branch:** `codex/update-14-book-details`.
- **Baseline:** `9f3ff9ec87634c696e60465347123b45dab83504`, verified on remote `main` after the user's authorized Update 13 upload and fast-forward merge.
- **Objective:** connect the specification's stored-book endpoint to a usable bilingual details/share page.
- **Actual scope:** frontend routes, shared catalog presentation, safe stored-book loading states, localized sharing, targeted regression checks and documentation. The existing backend is unchanged.
- **Working-tree boundary:** the authorized Update 13 changes were committed and published first. The tree was clean before creating this branch. No unrelated user changes were included.

The user explicitly requested merging the previous round into main and then starting the next task. Update 13 was committed as `fix: enforce named authors and preserve complete search streams`, pushed to its branch and fast-forward merged into main. Both remote refs were independently verified at the full baseline above. The author and committer were `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`. No additional author credits, collaborators, pull request, release or public deployment were added.

Update 13's opening status describes its earlier pre-confirmation review state. That historical wording is superseded by the explicit authorization and verified publication recorded here. Its complete 20-case gate passed before that merge; this record does not relabel that evaluation as a new Round 14 run.

## 2. Technologies used

No new dependency, framework, provider, paid service or database technology was introduced.

- **Existing Next.js 16.4.2 App Router and React 19.3:** add a dynamic `books/[isbn13]` route beneath the current locale. A server component reads stored public book information; a Suspense boundary supplies localized loading content while request-time data is resolved. The installed framework documentation was checked for asynchronous route parameters and Cache Components behavior.
- **Existing next-intl:** reuse locale-aware navigation and add English/Spanish messages. Switching interface language preserves the book identity and does not translate or mislabel its catalog language.
- **TypeScript and the native Fetch API:** distinguish recommendation cards from public stored details, validate ISBN checksums and response shapes, request a fresh stored snapshot and bound the backend read to five seconds. Expected failures become explicit result states rather than exposing raw upstream messages.
- **Existing React components, Tailwind utilities and next/image:** share the catalog layout between recommendation cards and details. Retain the existing visual style, cover fallback, ratings, descriptions, formats, bookstore links and availability disclaimer.
- **Browser Clipboard API:** copy a canonical current-origin book URL from an explicit button action. A read-only selectable input remains available, including when automatic copying rejects or is unsupported.
- **Existing Node native tests, ESLint, TypeScript/production build, pytest and native database/cache checks:** verify the changed frontend boundary and existing behavior. In-app browser automation exercised rendered interactions without installing browser packages.

## 3. Implementation

### Stored-book page

1. Open `/en/books/{isbn13}` or `/es/books/{isbn13}`.
2. Show the localized loading state while route parameters and stored data resolve.
3. Reject malformed or checksum-invalid ISBNs before making a backend request.
4. Read only `GET /api/books/{isbn13}` at the configured server-side backend address. This does not call the model, search providers or retailer lookups, and does not write a new search.
5. Request `no-store` behavior and apply a five-second timeout. This controls the detail read only; the existing 60-second search deadline, 70-second search proxy boundary and 15-second first-book target remain unchanged.
6. Validate identity and the data needed for rendering. A wrong ISBN, malformed arrays, bad dates, invalid rating data, unsafe link scheme, malformed JSON, rejected HTTP response or connection failure cannot be treated as a successful detail snapshot.
7. Render the book's public catalog information, original book language, readable source label and UTC snapshot date. Catalog descriptions remain original plain text. Null ratings/covers retain the existing fallbacks.
8. Present distinct localized invalid-link, not-saved and temporary-unavailable states. Temporary failures offer a full-page retry so a cached failed client navigation cannot prevent recovery.

The page does not display a reader's request, rank or recommendation reason. The backend already excludes these from the stored-book response. This round does not create a shared search-history endpoint.

### Recommendation entry and common presentation

`BookDisplay` now owns the existing catalog-only presentation. `BookCard` supplies its search-specific reason/disclaimer and a locale-aware detail link. Cards show that link only when the stream has reached `done` **and** no error was reported. The distinction matters because the backend sends a terminal `done` after error cases too. A partly emitted or unsuccessfully persisted search must not expose a newly saved-detail promise.

Detail links disable speculative prefetching. The success flow remains the same stream with the same book order, reasons and bookstore URLs. No filter, author rule, prompt, ranking operation, source query or persistence constraint changed.

### Sharing and language

- Interface language links retain the ISBN, while a separate field states whether the book itself is English or Spanish.
- The copy action constructs a URL from the current origin plus `/{locale}/books/{isbn13}`. Existing URL query strings and fragments are not copied. A URL contains neither search text nor a recommendation reason.
- Successful copying announces localized feedback. A selectable labeled text field displays the exact link. On clipboard failure it is accompanied by manual-copy guidance.
- Sharing does not publish data to another service or invoke an operating-system share target. A localhost link remains local to the machine serving it; public cross-device sharing depends on a later reachable deployment.

### Layout and accessibility

The page retains the existing light interface, readable content width and bookstore disclaimers. Controls and the description disclosure have 44-pixel minimum targets, descriptions wrap as plain text, and status/error messages use appropriate live-region semantics. The title is an `h1` on details and remains an `h2` in results. The share button has visible focus treatment and the fallback field has an explicit label. The full small-screen page can scroll vertically; long URLs remain selectable within an input.

## 4. File changes

| File | Change and purpose | Before and after |
| --- | --- | --- |
| `frontend/app/[locale]/books/[isbn13]/page.tsx` | Added server-rendered bilingual detail route, loading/error states, language navigation, snapshot metadata and sharing. | No detail UI existed; saved books can now be opened directly by ISBN. |
| `frontend/components/BookDisplay.tsx` | Added reusable catalog presentation extracted from the existing card. | Catalog fields were embedded in the recommendation component; cards and details now share the same presentation and disclaimers. |
| `frontend/components/ShareBook.tsx` | Added the explicit copy action, canonical URL construction, localized feedback and selectable fallback. | No share control existed; a book can now be shared without a search payload. |
| `frontend/components/BookCard.tsx` | Modified to compose `BookDisplay` and add the saved-detail entry. | Reasons and catalog fields lived in one component; reasons remain card-specific and the new entry is conditionally available. |
| `frontend/app/[locale]/page.tsx` | Modified to pass successful-completion availability to each card. | There was no detail entry state; unfinished and failed streams now withhold that entry. |
| `frontend/lib/types.ts` | Modified to split common metadata from ranked cards and add `BookDetails`. | All frontend books required a rank and reason; public snapshots now have a distinct type with language/source/date. |
| `frontend/lib/book-details.ts` | Added ISBN/path helpers, bounded stored-book loading and expected-result validation. | The frontend had no stored-book loader; invalid identities and service failures now receive safe explicit states. |
| `frontend/messages/en.json` | Added English detail/share/error labels and the card entry label. | Existing search/card messages remain; the new flow is localized. |
| `frontend/messages/es.json` | Added intentional Spanish localization for the same flow. | Existing localization remains; the new flow works in Spanish as required. |
| `frontend/tests/book-details.test.mjs` | Added five focused loader/path regression tests. | No checks covered this frontend boundary; invalid identities, outages, malformed snapshots and private query/fragment exclusion are now covered. |
| `README.md` | Documented actual routes, use, backend loading, local-link limits and status boundaries; removed the now-completed UI item from remaining work. | Details were documented only as an API; users can now find and understand the interface. |
| `update_version/Lumen_Update_Version_14.md` | Added this implementation, verification and submission record. | This round had no update record; actual scope and limits are now reviewable. |

No files were deleted. No backend files, rule files, dependencies, lockfiles, database schema, migrations or public API formats changed.

## 5. Project benefits

- Completes the user-facing path from a real recommendation to a saved book and a reusable link.
- Keeps personal search context out of the shared link and stored-book UI.
- Prevents invalid or not-yet-saved detail entries from appearing on unsuccessful searches.
- Makes old catalog information identifiable by its snapshot date instead of implying current stock or an automatic refresh.
- Reduces layout drift by sharing catalog presentation while keeping recommendation reasons specific to their search.
- Adds the detail flow without model spending or new external services.

## 6. Future impact and compatibility

- **API/database:** additive frontend routes only. Existing search payloads, SSE events, stored records, foreign keys and `GET /api/books/{isbn13}` semantics are unchanged. No migration or backfill is required.
- **Dependencies/configuration:** no package or infrastructure change. The server page uses the existing `BACKEND_URL` convention, which must point to the reachable backend in a deployed frontend process.
- **Cost/usage/privacy:** the daily cap remains 100 actual attempts. Detail reads do not consume model attempts or the search admission allowance. No private search data is added to a URL, shared page, analytics service or database field.
- **Caches/refresh:** the frontend requests a fresh read of the stored snapshot, not a new catalog fetch. Automatic 30-day catalog refresh remains unfinished. No real usage counters or catalog history were cleared.
- **Deployment:** localhost links work only where the preview is reachable. No production domain, public service, release or deployment was created. Public proxy and durable budget operations still require follow-up.
- **SEO/status limits:** Next.js streams a localized page shell, so an error page can have HTTP 200 even when the API returned 404/422/503. This round does not implement status-aware SEO or per-book Open Graph/social preview metadata; the browser title remains Lumen. These are documented limits, not a claim of completed rich previews.
- **Identity/semantic limits:** the prior conservative author and relevance checks are unchanged. Sharing a validated stored ISBN does not add author authority resolution or stronger semantic matching.

## 7. Verification

| Check | Actual result and boundary |
| --- | --- |
| Frontend native tests, final run | **11 passed**: five new detail/path tests plus six existing stream/error tests. No live model calls. |
| Frontend lint | Passed with no lint findings. |
| Production frontend build | Passed, including TypeScript and both locale detail routes with partial prerendering. The existing 70-second search proxy setting remains active. |
| Backend offline regression suite | **332 passed in 3.94 seconds** in the normal local execution environment. An earlier restricted-environment attempt stalled and was stopped; it is not counted as a pass. |
| Actual PostgreSQL/Redis integration suite | **31 passed in 11.07 seconds**, using the established isolated test workflow. Final inspection found zero temporary test schemas and zero `lumen:test:*` fixture keys. |
| Actual stored-book HTTP reads | Saved `9788417346201` returned 200, without query/reason/rank/search ID/raw fields; missing valid `9780000000002` returned 404; checksum-invalid and malformed values returned 422. |
| Rendered entry flow | `/en` cached search `A sad literary novel about the sea and solitude` returned six real stored recommendations; the first detail link opened `9780330483292`, The Sea by John Banville. The description expanded and collapsed correctly. |
| Language and sharing | The Spanish Toine Heijmans page switched to English with the same ISBN and retained Spanish as the book language. Copy feedback and exact public URL appeared; pasting into an editable field confirmed the copied English URL. No search was submitted with that pasted URL. |
| Rendered error states | Spanish missing-book and English invalid-ISBN messages rendered with no framework overlay. A separate temporary localhost preview with an intentionally unreachable read backend rendered the localized unavailable state. Restoring that preview's backend and clicking retry loaded the correct book. The real backend was not stopped for the fault injection. |
| Responsive layout | Desktop/default preview, requested 375×812 portrait and 812×375 landscape checked. DOM measurements reported page widths 360 and 797 respectively, below the viewport widths; visible detail controls measured 44 pixels high. Temporary viewport override was reset. |
| UI identity/content/console | Intended URLs and Lumen title verified; meaningful catalog or error content rendered. No framework overlay or relevant warning/error was captured in the tested browser pages. |
| Final normal service checks | Proxied health, both home locales and both checked saved-book pages returned 200. The temporary port-3001 fault/recovery preview was closed; normal port-3000 preview remains running. |
| Model spending | Shared daily count was **61/100 before and after** this round's checks. The browser search used an already-existing completed result; detail/fault/recovery checks made no model calls. |

The Browser plugin skill was not available and no project Playwright workflow was configured. The available in-app browser automation was used for DOM/AX observations, real control interactions, console inspection, viewport changes and screenshots; no new browser package was installed. One role-based selector did not resolve the native description disclosure; its observed accessibility control was used successfully instead. This was an automation selector limitation, not a claimed product failure.

Desktop and mobile screenshots were saved outside the repository in the task's permitted visualization directory and inspected. They are review evidence, not uploaded project assets. Final source fingerprints were checked against the completed Round 13 report: 47 matched the recorded bytes exactly; `app/authors.py` and `evals/author_run.py` matched after CRLF-to-LF normalization because the authorized Git checkout applied Windows line endings. The initial raw-byte assertion identified that distinction rather than a source change. A separate Git comparison confirmed no changes to `backend/app` or `backend/evals` relative to the merged baseline. Whitespace, repository language and new attribution checks were completed for the actual changed file scope; configured sensitive values were absent from all 12 changed/new files.

The 20-query live ranking gate was **not rerun** because no model prompt, retrieval, ranking, search policy or backend source changed. Its existing passed Round 13 gate is preserved, not presented as new verification. No public deployment, load test, external retailer purchase, full cross-browser sweep, screen-reader session, denied clipboard-permission browser scenario, maximum text-size sweep or independent dark-theme implementation was verified. The app retains its existing light theme and introduces no animation. Those omissions do not become successful test claims.

## 8. Approvals and remaining work

The user authorized the Update 13 upload/main merge and starting the next implementation task. The stored-book details/share flow follows the existing specification and was planned in conversation before implementation. No major architecture, provider, core capability, schema, privacy or spending decision was introduced. The daily 100-attempt policy remains unchanged.

This round is complete locally and awaits its own upload confirmation. Remaining work includes automatic 30-day catalog refresh, public proxy/deployment preparation, durable budget accounting across Redis loss, richer sharing metadata and status-aware detail-page polish. Public deployment remains a separate action requiring explicit authorization.

For manual review, open `http://127.0.0.1:3000/es/books/9788417346201`, switch languages, expand the description, copy the link and paste it somewhere without submitting a search. To test the entry flow, complete a normal search and open a card's details link. Invalid/missing examples above exercise the localized messages without AI spending.

## 9. GitHub submission

**Proposed commit title**

`feat: add bilingual saved-book details and share links`

**Proposed commit description**

Saved books had a public metadata endpoint but no frontend details/share flow. Add English and Spanish ISBN routes that read the existing saved-book API, show catalog metadata and snapshot age, preserve book identity across interface-language changes and copy a public book URL without reader search text or recommendation reasons.

Share catalog presentation between cards and details; show detail entries only after successful stream completion. Add checksum/response validation, a five-second read timeout, localized invalid/missing/unavailable states, a full-page retry and selectable clipboard fallback. Document local-link, snapshot and streamed HTTP-status limitations. No backend, schema, provider, dependency, prompt, retrieval rule or usage limit changes.

Validation: 11 frontend tests, lint and the production TypeScript build passed; 332 offline backend tests and 31 native PostgreSQL/Redis integration checks passed. Real browser verification covered a cached six-card search-to-detail flow, bilingual navigation, description disclosure, copy/paste, missing/invalid states, isolated outage/retry recovery and desktop/phone layouts. Shared model usage remained 61/100. The unchanged backend's prior full 20-case gate is preserved and was not rerun for this frontend-only round.

See `update_version/Lumen_Update_Version_14.md` for exact files, actual checks, compatibility, omissions and remaining work.

**Actual status:** local, uncommitted implementation on `codex/update-14-book-details`. No Update 14 upload confirmation has been received. No Update 14 commit, push, pull request, main merge, release or public deployment has occurred. Previous-round authorization does not authorize uploading this new scope.
