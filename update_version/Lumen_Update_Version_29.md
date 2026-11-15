# Lumen Update Version 29

## 1. Basic information

- **Round:** 29.
- **Date:** 2026-11-15, Europe/Madrid.
- **Branch:** `codex/update-29-editorial-redesign`.
- **Baseline:** `80e5765af602827292f17229bab611d37b9207cf`, the clean merged main containing rounds 27 and 28.
- **Objective:** implement the approved literary-journal/old-bookshop design across bilingual search/results, narrow screens and saved-book details/sharing.
- **Actual scope:** frontend presentation, translated interface copy, locally hosted font/decorative assets and change documentation. No backend, database, search graph, provider, spending, deployment or package-dependency change.

The working tree was clean before the separate round-29 branch was created.
The user approved the visual direction, requested refinement, and then explicitly
requested implementation. The earlier instruction to show concepts before coding
was therefore satisfied before this implementation started. There was no
unrelated user work to include or overwrite.

### Previous-round upload and merge receipt

After explicit confirmation for both rounds, round 27 (`a48b1f7`, ten files) and
round 28 (`80e5765`, five files) were uploaded to their separate branches. Their
combined main change contains fourteen distinct files because both modify the
README. All three hosted jobs passed on each branch before a normal fast-forward
main synchronization. The main run also passed all three jobs:

- [Round-27 branch checks](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43658466807).
- [Round-28 branch checks](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43658466837).
- [Main checks at 80e5765](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43658955787).

The author and committer matched the verified owner identity. No force push,
pull request, release or deployment was performed. This supplies the subsequent
receipt for the checkpoint-preparation statuses preserved in records 27 and 28;
neither earlier record was rewritten. The upload confirmation for those rounds
does not upload this new round.

## 2. Technologies used

- **Next.js 16.4.2 / React 19.3 / TypeScript:** retain the App Router, existing partial prerendering, metadata lookup and client/server boundaries. Presentation changes reuse the existing search and copy state machines.
- **CSS and existing Tailwind build infrastructure:** introduce semantic design tokens, responsive grid/flex layouts, visible focus, native controls/disclosures and reduced-motion styling. A small monochrome SVG texture gives the exact ivory background a subtle paper character without an external image service.
- **`next/font/local`:** replace the unused generic font setup with locally hosted literary and reading faces. Three Latin WOFF2 files total 84,308 bytes. Source font licenses remain with the files; no font package or runtime font CDN was added.
- **`next/image`:** retain real catalog covers and serve a separate transparent decorative engraving. The illustration contains no app UI or bibliographic text and never substitutes for a real book cover.
- **next-intl:** add matching English/Spanish hero, results, footer and sharing copy while retaining existing errors, constraints and privacy feedback.
- **Playwright Core 1.64.0 / Chromium 156.0.8078.4:** verify actual production pages, native controls, focus/selection, responsive layout and browser logs. The Browser plugin is absent (`Browser plugin not available`); the already-installed local browser tooling was used without installing or changing dependencies.
- **Python standard-library loopback fixture:** supply controlled book/SSE/error responses from retained public catalog evidence without opening a database or creating a model/catalog-search client.

No new application framework, model provider, paid service or package dependency
was introduced. Official font sources and licenses are documented in
`docs/editorial-design.md`; third-party font notices do not assign project
authorship.

## 3. Implementation

### Visual system and shared chrome

The interface uses warm ivory `#F5F1E8`, ink `#26372F`, forest actions `#29483C`,
terracotta `#A3543A` and fine warm rules. Locally hosted Libre Baskerville supplies
the literary normal/italic typography; Source Sans 3 supplies readable text and
fields. The matching book engraving has transparent edges and no color wash.
The wordmark, headings, controls and all public catalog text remain code-native.

Shared chrome supplies the Lumen wordmark, active-locale underline and footer.
Shared thin SVG icons supply directional arrows, copy and disclosure affordances
without redundant accessible names. A skip link bypasses the repeated header;
browser verification covers both initial home and client-navigated detail pages.

### Search and results

The home page now has the approved two-line literary heading, supporting copy,
decorative desktop engraving, open search form and three existing optional
filters. Native validation, query/filter values, request serialization, progress,
cancel, error recovery, locale reset and bounded recommendation handling are
unchanged. The decorative illustration is hidden on narrow screens.

Recommendations are open editorial rows instead of nested bordered cards. Each
row presents its actual rank, catalog cover or honest missing-cover label, title,
authors, available metadata, formats and source-labelled rating. The actual
streamed reason appears under a localized label and retains its AI-generation
notice. Description disclosures, all returned store channels and their caveat
remain available. Detail/share links remain gated on successful completion.
Book headings use `h3` below the results `h2`, without changing their visual role.

The page never substitutes the illustrative concept jackets or reasons for real
catalog responses. Missing authors/dates/page counts/descriptions/formats/channels
remain missing; the interface does not invent replacements.

### Saved-book details and sharing

The saved-book page uses matching chrome, back/locale navigation, a larger real
cover and balanced serif title, the existing description and source-derived
purchase channels. Its source/date/ISBN/language information remains explicit.
The existing five-second bounded no-store lookup, request-local metadata/page
reuse, error states and noindex behavior are unchanged.

The sharing region has a clear heading, retained search/reason privacy message
and copy action. The existing origin/locale/ISBN-only URL construction, pending
button, success message, manual fallback and automatic focus/selection remain.
No public domain, stock, price, rating or social-platform success is invented.

### Responsive and accessible behavior

At narrow widths the search action and filters stack, headers can wrap, and
cover columns are bounded by a share of available width. Enlarged text therefore
does not consume the entire information column. Long metadata, errors, reasons
and expanded descriptions reflow. Fields and primary actions have generous
minimum heights; links/disclosures retain at least 44px targets. Inputs retain
at least 16px text, including manual copying. Focus is visible and the skeleton
respects reduced motion.

The first comparison exposed undersized field text and an overly long desktop
detail title line. Text/controls were enlarged and the title was balanced within
a bounded measure. A palette check found an initial 2.96:1 field-boundary ratio;
the final border was darkened before the full final browser pass. Existing
warnings and actual data can produce taller rows than the illustrative concepts.

## 4. File changes

| File | Change and before/after purpose |
| --- | --- |
| `frontend/app/globals.css` | Modified: replace generic white/zinc presentation with shared editorial tokens, type, paper texture, controls, open book rows, responsive details, focus and motion rules. |
| `frontend/app/[locale]/layout.tsx` | Modified: replace generic remote-build font declarations with vendored local faces and add the translated skip link; retain locale/provider ownership. |
| `frontend/app/[locale]/page.tsx` | Modified: apply the approved header/hero/form/results/footer composition while preserving existing search, locale and recovery logic. |
| `frontend/app/[locale]/books/[isbn13]/page.tsx` | Modified: apply the matching book/share composition and grouped metadata strip while retaining the existing lookup, metadata, locale and error behavior. |
| `frontend/components/BookDisplay.tsx` | Modified: replace compact card framing with shared result/detail layouts, real covers, metadata, sourced ratings, disclosures and channels. |
| `frontend/components/BookCard.tsx` | Modified: present actual rank/reason, localized reason label and the completion-gated detail action within the editorial row. |
| `frontend/components/BookCardSkeleton.tsx` | Modified: match row geometry and bound placeholder widths; narrow screens omit the empty rank column. |
| `frontend/components/ShareBook.tsx` | Modified: apply the editorial sharing region and copy icon while retaining URL, pending, fallback and selection logic. |
| `frontend/components/Icons.tsx` | Added: consistent decorative SVG arrows, copy and disclosure icons. |
| `frontend/components/SiteChrome.tsx` | Added: reusable text wordmark/header and translated footer. |
| `frontend/messages/en.json` | Modified: English hero/results/chrome/share copy and approved action labels; existing functional/error/privacy text retained. |
| `frontend/messages/es.json` | Modified: corresponding intentional Spanish interface copy and labels. |
| `frontend/app/fonts/literary-regular.woff2` | Added: compact locally hosted normal literary face instead of relying on a visitor's font download from a third party. |
| `frontend/app/fonts/literary-italic.woff2` | Added: matching italic face for the approved heading/footer treatment. |
| `frontend/app/fonts/reader-regular.woff2` | Added: compact locally hosted reading/control face. |
| `frontend/app/fonts/LibreBaskerville-OFL.txt` | Added: original third-party font license, retained unchanged. |
| `frontend/app/fonts/SourceSans3-OFL.txt` | Added: original third-party font license, retained unchanged. |
| `frontend/public/images/books-engraving.png` | Added: transparent decorative book engraving matching the accepted hero; not a catalog cover or screenshot of UI. |
| `docs/editorial-design.md` | Added: accepted visual inventory, copy, component ownership, responsive/correctness constraints and official font sources. |
| `README.md` | Modified: describe the implemented local visual system and link its design documentation. |
| `update_version/Lumen_Update_Version_29.md` | Added: this implementation record and the prior-round upload/main receipts. |

Twenty-one files form this round's submission scope. No existing file, earlier
record or failed capture was deleted or overwritten. Temporary original TTF
downloads created for this task were replaced by smaller official WOFF2 files
before verification; these were never tracked baseline files.

## 5. Project benefits

Search and sharing now read as one coherent literary product rather than a
collection of generic controls. Clearer hierarchy, larger fields and orderly
book rows improve scanning while preserving access to actual catalog evidence.
Locally served assets avoid introducing visitor font-CDN requests. Shared
presentation and icon/chrome ownership reduce styling duplication. Existing
keyboard and error recovery remain usable after the visual changes.

## 6. Future impact and compatibility

No backend API/SSE shape, database migration, candidate/ISBN validation, foreign
key, search graph, prompt/retrieval rule, cache identity, source integration,
provider or spending policy changed. The normal daily setting remains 100;
the original ledger was not opened, initialized, reset or modified.

The frontend adds three font files and one decorative image, plus localized
presentation copy. No package or lockfile changed. The engraving continues
through the existing local image optimization path. Browser/source fixtures
cannot establish production capacity, new recommendation latency or complete
semantic relevance. Real catalog covers may be lower resolution than concept
art; the UI must preserve their identity rather than replace them for appearance.

Rollback is limited to the frontend/documentation/asset changes and requires no
database operation. Future changes should reuse the documented visual tokens
and component families. Public deployment, canonical origin, backup decisions,
HTTP-status-aware streamed detail errors and real social-platform checks remain
separate work.

## 7. Verification

The tested flow was: localized home -> search/progress/results or recovery ->
saved-book details -> public link/copy feedback, including locale switching,
native disclosure and keyboard navigation.

| Check actually performed | Result |
| --- | --- |
| Existing frontend tests | **46 passed**, zero failures/cancellations/skips. Retained native Node module-type notices were not hidden or resolved by changing package semantics. |
| Frontend ESLint | Passed without disabling checks. |
| Final production Next.js/TypeScript build | Passed; all nine static outputs generated and partial prerendering retained. Earlier comparison builds also passed. |
| Main final Chromium matrix | **190/190 scenario checks**, across English/Spanish at 1280x900, 375x812, 320x740, 844x390 with dark preference, and 375x812 with 200% root text/reduced motion. |
| Supplementary final flow checks | **20/20 scenarios** across both languages at 375px/1280px: Enter/filter payload, description toggling, protected store links, same-ISBN locale navigation, preference reload/URL precedence and no late cards after in-flight locale change. |
| Additional keyboard/missing-data checks | **12/12 scenarios** at 375px/1448px in both languages: skip navigation reaches the visible home/detail controls; missing metadata gives honest cover/rating feedback without invented text, disclosure or channels. |
| Combined final browser result | **222 scenarios and 1,030 individual assertions passed**. These are controlled interface checks, not 222 new model searches. |
| Identity, blank pages and overlays | Expected page titles/routes, visible meaningful content and no framework overlay verified. |
| Browser health | No relevant app console warnings/errors or page exceptions in the main final matrix; no unexpected external-origin browser requests. Thirty exact local 429/503 resource notices were expected from deliberately exercised error responses and retained separately. |
| Layout and typography | No horizontal overflow in the tested states. Enlarged-text loading documents stay 375px wide. Local literary/reading faces loaded; root ivory is `rgb(245, 241, 232)`. Manual links retain at least 16px text. |
| Visual comparison | Actual desktop search/details captured at the accepted 1448x1086 dimensions, plus 375px narrow views. Reference and implementation images inspected for composition, copy, type, palette, assets, row geometry and controls. Larger fields and balanced title corrected the initial comparison differences. |
| Final contrast | The darkest sampled paper pixels in the final screenshot give 10.76:1 ink, 5.49:1 muted text, 4.62:1 accent, 3.22:1 field boundary and 8.61:1 primary fill contrasts. This is a scoped palette/sample check, not a complete accessibility certification. |
| Catalog image verification | Nine existing public cover URLs were retrieved successfully for the controlled visual captures. This is image availability evidence at test time, not catalog-search quality or future availability. Functional fixtures may use controlled cover responses. |
| Retained recommendation evidence audit | Verified the existing complete 20-case, 144-card capture against unchanged recommendation sources. No new live 20-query evaluation or backend/database integration run: recommendation sources and persistence code are unchanged. Historical usage/cap values belong to the original capture, not today's allowance. |
| Cleanup | Verified and stopped only the owned UI/fixture processes; ports 3048/8047 closed. Original backend/PostgreSQL/Redis containers remained stopped and original volumes were not accessed. |
| Submission review | Exact twenty-one-file scope, unchanged tested implementation, matching owner identities, bilingual message-key parity and configured-secret/attribution/language checks verified. New project text has no trailing whitespace. The two official font licenses retain upstream whitespace at line 21; their original bytes were checked against the downloaded source fingerprints rather than rewriting legal notices. |

The production UI used loopback port 3048 and a controlled fixture on 8047.
Original backend/PostgreSQL/Redis containers remained stopped. Clipboard success,
delayed rejection and immediate repeated rejection were simulated within isolated
browser contexts; the operating-system clipboard was not read or overwritten.
No real model request, catalog metadata/search query or database operation was
performed by these UI tests. Nine cover-image GETs are reported separately above.

Final UI evidence, earlier comparisons, ARIA snapshots, logs and tested-source
fingerprints remain outside Git in `round29-ui-qa`. The first palette capture
retains the insufficient field-boundary measurement, with a separate final
contrast result. No threshold was lowered and no failed result was relabelled.
The final seven-point fidelity ledger and approved-copy comparison are retained
there too. The tested implementation fingerprints match the final files;
completion of this record changes documentation only.
An initial final-review assertion also flagged the two unmodified font-license
lines. The review now distinguishes original, source-verified third-party legal
formatting from newly authored project text; no license or source was changed to
hide that result.

The final fidelity differences are deliberate production constraints recorded
before coding: catalog covers/titles/reasons and channel counts vary, mandatory
filter/source/privacy notices remain, and the mobile concept's 1024px raster is
an art-direction reference rather than a literal CSS viewport. Actual narrow
layout is verified at 320px/375px. The application follows the accepted visual
system; no claim of pixel identity for changing catalog content is made.

Safari, Firefox, physical devices, native clipboard permissions, real share
platforms, public ingress, production load, new provider authentication and new
first-book latency were not tested. The checks do not constitute a full formal
accessibility certification or production-release approval.

## 8. Approvals and remaining work

The approved design and explicit implementation request cover this routine
presentation change within the existing MVP. No new major architecture, schema,
provider, product-scope or spending decision was required. No paid host, public
domain, release, scheduler, backup policy or deployment was activated. The user
steered this next round to visual implementation; deployment choices remain
pending under the existing proposal.

No reproduced functional defect remains open within the final tested matrix.
Cross-browser/device and real public-platform validation remain outside this
local round. Real covers retain their source quality and may change or fail
independently. Further user-directed visual refinements can remain on this branch
before its reviewed upload scope is confirmed.

## 9. GitHub submission

**Proposed commit title:** `feat: apply the approved editorial book design`

**Proposed commit description:**

Replace the generic bilingual search and saved-book presentation with the
approved literary-journal design: warm ivory paper, forest actions, locally
hosted serif/reading typography, a matching decorative engraving and open book
rows. Share the wordmark/footer/icon vocabulary and apply it consistently to
search, loading/error recovery, details, catalog metadata and public copying.

Keep actual catalog covers/bibliography, source-labelled ratings, streamed
reasons and their notices, optional filters, native disclosures, channel caveats,
completion-gated detail links and origin/locale/ISBN-only sharing. Retain existing
locale, cancellation, stale-result protection and manual-copy focus/selection
behavior. Reflow headers, forms and bounded cover columns on narrow/enlarged-text
views. Preserve the bounded saved-book lookup and metadata reuse.

Verification: 46 existing frontend tests, ESLint and the production
Next.js/TypeScript build passed. The final controlled Chromium checks passed
222 scenarios with 1,030 assertions in both locales, including 320px, landscape,
200% text, errors, copying, filtering, navigation and missing metadata. Compare
real desktop captures at 1448x1086 with the approved references and retain the
initial/final palette and visual evidence. Nine existing cover-image GETs were
successful; no new recommendation-model, catalog-search or database calls were
made. The browser evidence is separate from a live recommendation acceptance or
public deployment test.

No backend/API/schema, graph/prompt/retrieval, provider, package dependency,
deployment or daily-policy change. Rollback needs no migration. Include local
font licenses and document the visual system, compatibility, actual evidence and
public/cross-browser limits in `docs/editorial-design.md` and
`update_version/Lumen_Update_Version_29.md`.

**Status at local checkpoint preparation:** after reviewing the local design,
the user requested switching the whole project to Docker. The twenty-one
reviewed files are being saved in a local-only commit so the Docker transition
can use a separate branch with an explicit dependency baseline. No round-29
upload, pull request, main merge, release or public deployment has occurred.
Separate reviewed upload confirmation remains required; the earlier upload
confirmation applied only to rounds 27 and 28. The next record will identify
the actual local checkpoint and the Docker transition results.
