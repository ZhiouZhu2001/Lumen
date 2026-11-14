# Lumen Update Version 27

## 1. Basic information

- **Round:** 27, an implementation round rather than an application release.
- **Date:** 2026-11-14, Europe/Madrid.
- **Branch:** `codex/update-27-book-share-metadata`.
- **Known baseline:** `c2ae9199ba7cc27cd0b7478c40416885cb077b26`, verified on local and remote main before creating this branch.
- **Objective:** give saved-book links useful localized sharing previews while preserving public-data boundaries and the existing bounded detail lookup.
- **Actual scope:** server-generated book metadata, request-local lookup reuse, three new translation keys per language, 25 new frontend tests, controlled production HTTP captures and documentation; ten public files.

### Round 26 merge receipt

The user explicitly authorized merging the reviewed eight-file round into main
and starting the next round. Pending files matched the existing reviewed
fingerprints before the submission-status update. Public-content, owner-identity,
whitespace, lint/format and retained-evidence checks passed. No new real-model
acceptance was required for that file-only diagnostic/documentation scope.

Commit `c2ae919` was created with the complete English description and verified
sole-owner author/committer identity, then uploaded. All three
[branch checks](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43529773037)
passed. Main was fast-forwarded and remote main was verified at the same commit;
all three [main checks](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43530303681)
also passed. The new round began from a clean tree on that exact baseline.
No force push, pull request, release, deployment or collaborator change occurred.
This receipt closes the preparation-time upload status in the preserved
round-26 record; its authorization does not upload round 27.

## 2. Technologies used

No dependency, framework, model provider or paid service was added. Existing
Next.js 16.4.2 Metadata APIs produce page/Open Graph/Twitter fields. Existing
React request-local `cache` shares the bounded server lookup, and next-intl
provides English/Spanish copy. TypeScript keeps the public book-result boundary
explicit. Node's native test runner verifies pure metadata behavior; ESLint and
the production Next.js/TypeScript build verify integration. HTTPX and a Python
standard-library loopback fixture check actual production HTTP responses without
using the original database, model or real catalog services.

The installed Next.js guides were checked before implementation, including
dynamic metadata, streaming metadata, Cache Components and fetch memoization.
The existing detail loader supplies an abort signal, which opts out of automatic
fetch memoization; explicit request-local result reuse avoids duplicate lookups.

## 3. Implementation

The detail route now exports `generateMetadata`. It reads only locale and ISBN
route parameters, validates the supported locale and loads translations alongside
the same stored-book result used by the page. Its request-local cached function
uses a primitive ISBN argument. The original loader still validates ISBN/checksum,
checks returned identity and payload shape, uses `cache: no-store` and applies
the existing five-second timeout. No persistent cross-request cache is added.

Successful previews identify the original catalog title, available authors and
ISBN with localized surrounding copy. They supply matching page, Open Graph and
Twitter titles/descriptions. A usable cover produces a large-image card; an
absent/unusable cover produces a text summary. Missing authors are omitted.
Source descriptions, search text, recommendation reasons and incoming query
parameters do not supply preview content. No source catalog record is changed.

The pure metadata helper normalizes/bounds text without splitting Unicode code
points. It accepts only absolute HTTPS image URLs on the two existing cover
hosts, rejecting credentials, nonstandard ports, fragments and recognized
key/token/search/reason parameters. These are metadata image rules; they do not
change the existing visible book-card implementation or prove image availability.

Invalid ISBNs, missing books and unavailable/malformed replies produce distinct
localized descriptions, generic unavailable titles, no preview image and
`noindex, nofollow`. An empty visible catalog title also uses unavailable
metadata. Unsupported locale handling avoids a book lookup. Existing language
middleware retains its relative 307 redirect to the default locale and final
404 for an unmatched path.

The page skeleton, visible book presentation, copy-link control, API proxy,
Cache Components configuration and default bot list remain unchanged. Regular
clients can receive metadata later in the HTML stream; recognized HTML-limited
bots receive it in the initial head. No canonical origin, public domain or author
profile URL is invented. Existing streamed detail-error responses can remain
HTTP 200; HTTP-status-aware detail errors are separate follow-up work.

## 4. File changes

| File | Change and before/after purpose |
| --- | --- |
| `frontend/app/[locale]/books/[isbn13]/page.tsx` | Modified: replace inherited generic metadata with localized book metadata and reuse one bounded result between metadata/page rendering; existing visible states remain. |
| `frontend/lib/book-metadata.ts` | Added: pure public-bibliography preview construction, bounded text, cover rules, summary fallback and safe noindex error metadata. |
| `frontend/messages/en.json` | Modified: add English descriptions with/without authors and preview-cover alternative text. |
| `frontend/messages/es.json` | Modified: add the corresponding intentional Spanish interface translations. |
| `frontend/tests/book-metadata.test.mjs` | Added: 25 metadata tests covering both locales, bibliography, privacy, Unicode, missing data, noindex states and cover URL restrictions. |
| `backend/evals/results/book-share-20261114-round27.json` | Added: initial controlled 28-case production HTTP capture, retaining one failed direct-404 assumption for unsupported locale handling. |
| `backend/evals/results/book-share-20261114-round27-verified.json` | Added: separate successful 28-case controlled production capture, including the existing relative 307 redirect followed by final 404. |
| `docs/book-sharing.md` | Added: public-data/request behavior, preview fields, image/error rules, streaming/status boundaries, controlled evidence and remaining platform/deployment work. |
| `README.md` | Modified: describe implemented sharing previews and retain the distinct canonical-origin, HTTP-status and public-platform follow-up boundaries. |
| `update_version/Lumen_Update_Version_27.md` | Added: this implementation record and actual round-26 merge/check receipts. |

No file was deleted and no earlier report/update record was overwritten. Private
fixture/check helpers, build/server logs and verification manifests remain
ignored under `backups/`.

## 5. Project benefits

Book links now carry identifying bibliographic previews instead of only a generic
site title. Localized descriptions and cover alternatives work in both supported
interfaces. Unavailable links avoid misleading book previews and are marked
against indexing. Request-local reuse prevents metadata generation from doubling
the existing detail lookup while allowing later requests to observe updates.
Public preview content retains the existing search/reason privacy boundary.

## 6. Future impact and compatibility

No backend API/SSE schema, database migration, graph, prompt, retrieval rule,
dependency, provider, store link or spending policy changed. The normal daily
model cap remains 100. This round reserves no model allowance and does not
initialize, reset or modify the original usage ledger.

The existing five-second detail bound and no-store behavior remain. Sharing
crawlers may request book pages and cover images, but no new direct catalog
client or background work is introduced. Actual social platforms can cache
previews independently; local snapshot updates do not guarantee immediate
third-party changes. New preview fields are additive; existing copied links
still contain only origin, locale and ISBN.

An approved canonical public origin, HTTP-status-aware streamed detail errors,
real share-platform checks and public deployment remain future work. Cover URL
validation is not proof of asset availability. The existing recommendation-source
fingerprint inventory excludes frontend code, so the retained backend acceptance
audit alone does not validate this round; the frontend build and controlled
production checks provide its additional evidence.

## 7. Verification

| Check actually performed | Result |
| --- | --- |
| Full native frontend test suite | **46 passed**, zero failures/cancellations/skips; 25 new tests plus the existing 21. |
| Frontend ESLint | Passed without disabled rules. |
| Production Next.js build and TypeScript | Passed; compiled successfully, TypeScript completed and all nine static outputs generated. Book-detail routes retain partial prerendering. |
| Initial controlled production HTTP probe | 27 of 28 cases passed. The unsupported-locale case returned the existing relative 307 redirect with zero book requests rather than the harness's assumed immediate 404. Original capture retained unchanged. |
| Corrected controlled production HTTP probe | **28 of 28 passed** across English/Spanish, regular/HTML-limited-bot requests, valid/invalid/missing/outage/wrong-identity data, absent covers, privacy parameters, fresh cross-request covers, timeout and unsupported locale routing. |
| Actual request reuse | Each valid/missing/outage/malformed/timeout request made one upstream book lookup shared by metadata and page. Invalid ISBN and unsupported locale requests made zero. |
| Crawler delivery | Recognized bot responses included Open Graph title metadata in the initial head. Regular responses contained the completed streamed metadata. No client-side browser execution was claimed. |
| Existing timeout and freshness | The slow fixture produced safe unavailable/noindex metadata within the existing timeout. Later requests saw a changed cover size or no-cover result, proving no persistent memoization was introduced. |
| Source/report agreement | Both captures' four frontend LF-normalized source fingerprints match the final implementation. No source change was used to correct the locale test expectation. |
| New backend/database/real recommendation tests | Not run: backend, models, graph, prompts and retrieval are unchanged. Fixture verification uses no database or real model/catalog service and is explicitly not the 20-case recommendation gate. |
| Public platform/image/browser/deployment verification | Not performed: no approved public host/origin exists; no claim about real platform caching, live image availability, clipboard permissions or visual layout is made. |
| Cleanup | Verified and stopped only the owned native production frontend and fixture server; ports 3047/8047 closed. Original backend/PostgreSQL/Redis containers remained stopped; original volumes were not used by these tests. |

The first probe's direct-404 assertion was corrected after inspecting the
unchanged locale middleware. A follow-up harness also initially assumed an
absolute Location header; the actual relative path was resolved against the
verified loopback origin before following it. The final check asserts both the
307 target and final 404 with no book request. Prior failure evidence remains;
no implementation, acceptance threshold or recommendation check was weakened.

Production captures explicitly state `fixture_backend: true`,
`full_recommendation_gate: false`, zero new model/catalog calls and no database
use. They validate real local production HTTP output against controlled data,
not live bibliographic quality, public ingress or new recommendation latency.

## 8. Approvals and remaining work

The user's instruction to start the next round covers this routine sharing
polish within the existing saved-book capability. No major architecture,
provider, schema, spending or scope decision was required. No new service,
domain, release or deployment was activated. English remains the repository
language, with intentional Spanish interface/test output preserved.

Round-26 upload/main synchronization was explicitly authorized and completed.
Round 27 requires separate reviewed upload confirmation; that earlier permission
does not publish these ten files. Future merge/release/deployment steps need
their corresponding authorization. Public origin and backup/host policy decisions
remain pending under the existing deployment proposal.

## 9. GitHub submission

**Proposed commit title:** `feat: add localized previews for saved book links`

**Proposed commit description:**

Saved-book links previously inherited generic site metadata. Generate localized
page/Open Graph/Twitter previews from validated public catalog title, authors,
ISBN and usable covers, while excluding source descriptions, search text and
recommendation reasons. Provide safe noindex error states, bounded Unicode text,
cover URL restrictions and a no-image summary fallback without inventing a
canonical public origin or bibliography.

Share the existing bounded no-store lookup between metadata and page using a
request-local React cache. Preserve later-request freshness, the five-second
timeout, visible page states, locale routing, copy-link behavior and streaming
configuration. Add 25 frontend regressions, controlled production captures and
sharing documentation. No backend API/schema, model graph/prompt/retrieval,
dependency, provider or daily-policy changes.

Verification: 46 frontend tests, ESLint and the production Next.js/TypeScript
build passed. The separate final controlled HTTP capture passes 28 cases,
including crawler-head metadata, privacy parameters, one upstream lookup,
cross-request updates, timeout and relative locale redirect/final 404 behavior.
Retain the initial failed harness expectation and its explanation. No real
model/catalog/database calls, public-platform tests or deployment occurred.
See `update_version/Lumen_Update_Version_27.md` and `docs/book-sharing.md` for
compatibility, evidence boundaries and remaining work.

**Status at local checkpoint preparation:** after implementation, the user
requested the next round without authorizing round-27 upload or main
synchronization. The ten reviewed files are being saved as a local-only
checkpoint so the next round has an explicit dependency baseline. Round 27
remains unapproved for GitHub upload and has not been merged, released or
deployed. The next update record will identify the actual local commit.
Remote main remains `c2ae919`; the successful hosted checks above concern round
26. Any later upload must separately review and authorize the dependent rounds.

Final review verified the exact ten-file scope, both captures against the final
frontend source fingerprints, no configured secret matches, English explanatory
content with intentional Spanish localization, no unwanted attribution and no
trailing whitespace. Recommendation sources, the existing detail loader, proxy
configuration and the normal 100-attempt policy remain unchanged. Owner Git
identities still match the verified configuration. No files were staged and no
round-27 commit, upload or merge was performed.
