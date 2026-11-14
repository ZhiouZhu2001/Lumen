# Lumen Update Version 28

## 1. Basic information

- **Round:** 28.
- **Date:** 2026-11-14, Europe/Madrid.
- **Branch:** `codex/update-28-final-ui-regression`.
- **Implementation baseline:** `a48b1f75ee3d6f4338ae2b2f319949524561458e`, the local round-27 checkpoint.
- **Local and last-known remote main:** `c2ae9199ba7cc27cd0b7478c40416885cb077b26`, round 26. No remote fetch, upload or main update was performed in this round.
- **Objective:** verify the bilingual search-to-book-sharing flow across desktop, narrow/mobile and enlarged-text views, and correct reproduced interface defects within the existing MVP.
- **Actual scope:** three frontend files, the README and this record. No backend, dependency, API, database, model, retrieval, deployment or spending-policy change.

Before creating this branch, the ten reviewed round-27 files were saved in the
local-only commit `a48b1f7` (`feat: add localized previews for saved book links`).
The owner author and committer identities were verified. The working tree was
clean at the new branch baseline, with no unrelated changes carried into this
round. That checkpoint establishes a dependency; it is not an upload or merge.
Round 27 remains separately unapproved for upload. This receipt supplies the
actual commit after the checkpoint-preparation status recorded in version 27;
the earlier record was not rewritten.

## 2. Technologies used

- **React 19.3 refs and effects:** restore focus after a search state transition or after a newly rendered manual-copy field becomes available. Primitive status/URL dependencies avoid rerunning the effects for unrelated renders.
- **Next.js 16.4.2 and TypeScript:** build and serve the existing production application, including the saved-book routes and their existing partial prerendering. Installed Next.js CSS guidance was consulted before layout edits.
- **Tailwind CSS:** allow the existing search/cancel group to wrap, constrain a loading placeholder to its column, and use the existing base text size for the share field.
- **Native Node tests and ESLint:** run the existing functional frontend suite and code checks without adding class-string tests that duplicate the layout implementation.
- **Playwright Core 1.64.0 and Chromium 156.0.8078.4:** exercise actual rendered controls, focus, selection, responsive layout, navigation and console behavior. The Browser plugin was absent: `Browser plugin not available`. The repository has no configured browser-test workflow; a no-install package check found no project Playwright package. An already-installed local Playwright Core and cached browser were used without modifying that installation or adding project dependencies.
- **Python standard-library loopback fixture:** supply controlled SSE/error/book responses from retained public bibliographic cards. It creates no model, catalog or database client. Browser cover responses and clipboard outcomes are controlled separately.

No new application technology or dependency was introduced. Temporary scripts,
browser captures and logs remain outside the repository in the local
`round28-ui-qa` verification directory.

## 3. Implementation

### Search recovery

Previously, disabling the request field during a search and removing the cancel
button could leave focus on the document after cancellation or failure. The home
page now keeps a ref to the existing request field. After the search enters
`error` or `cancelled`, an effect focuses that field after React has re-enabled
it. Successful results retain their existing focus behavior. Query, filter,
stream, cancellation and error-state logic are unchanged.

### Manual sharing recovery

Previously, a denied clipboard write displayed the manual-copy message but did
not focus or select the public link automatically. The share component now
focuses the field when the fallback state is rendered. The existing focus
handler selects the entire link. The rejection handler also focuses an already
mounted field, covering an immediate repeated rejection whose state updates can
be batched without a new effect transition.

The share input changes from `text-sm` to `text-base`: measured default text is
16px instead of 14px, and scales to 32px in the enlarged-text checks. This
improves readability; it is not a claim about native Safari zoom behavior.
Copying still uses the origin, interface locale and ISBN only, discarding query
parameters and fragments. The existing pending-button state and localized
feedback remain.

### Enlarged-text loading layout

At 375px with the root text size set to 200%, the original loading controls made
the document 470px wide in English and 496px in Spanish. The search/cancel group
now allows wrapping and can shrink within its parent.

The first retest exposed a separate remaining 385px document width: the loading
card's fixed-width button placeholder exceeded its narrow text column. Applying
`max-w-full` constrains that placeholder while retaining its normal preferred
width. Both languages now measure a 375px document within a 375px viewport while
loading at 200% text size. Reduced-motion behavior remains intact.

Normal-size long-word stress content already reflowed correctly at baseline;
the existing card wrapping was retained. This round does not redesign the UI.

### Documentation correction

The README explains the recovery and reflow behavior. It also corrects a stale
sentence that still excluded rich sharing previews after round 27 implemented
their metadata. The separate streamed HTTP-status limitation remains explicit.

## 4. File changes

| File | Change and before/after purpose |
| --- | --- |
| `frontend/app/[locale]/page.tsx` | Modified: previously cancellation/failure could lose useful focus and the loading controls could not wrap; now focus returns to the enabled request field and the button group wraps within the form. |
| `frontend/components/ShareBook.tsx` | Modified: previously clipboard rejection only displayed feedback and the link used 14px text; now fallback focuses/selects the link, including immediate retries, and uses the base 16px text size. |
| `frontend/components/BookCardSkeleton.tsx` | Modified: previously the preferred placeholder width could exceed an enlarged-text column; now its width is bounded by that column. |
| `README.md` | Modified: document the recovery/reflow behavior and replace the outdated preview exclusion with the implemented metadata and remaining HTTP-status boundary. |
| `update_version/Lumen_Update_Version_28.md` | Added: this round's implementation, dependency receipt, verification, limits and proposed submission description. |

No file was deleted. Earlier records, failed captures and acceptance thresholds
were preserved. These five files are the round-28 scope relative to `a48b1f7`;
the ten-file round-27 checkpoint is an earlier dependency, not new round-28 work.

## 5. Project benefits

Keyboard users can immediately revise a failed or cancelled search. Clipboard
restrictions lead directly to a selected, readable public link instead of
requiring another navigation step. Enlarged text no longer creates the
reproduced horizontal overflow during loading. The changes strengthen the
existing search/share flow without additional network requests or model cost.

## 6. Future impact and compatibility

No API/SSE contract, schema, migration, source integration, model prompt,
candidate validation, foreign key, provider, store rule or package lock changed.
The fixed graph, two broadening retries, shortlist limits and existing real-book
validation remain. The normal daily setting remains 100; no ledger was opened,
initialized, reset, reconciled or modified by these checks.

The share field's default font increases by 2px. Enlarged controls may occupy
additional vertical space as they wrap; ordinary desktop layout remains the
existing design. Error/cancel transitions and clipboard rejection now move
keyboard focus intentionally. No new automatic focus is added to successful
search completion or successful copying.

The implementation is reversible through the three frontend edits, with no
data rollback. A future deployment still needs the approved public origin,
ingress, backup and release decisions described in
`docs/production-deployment.md`. This round activates none of them.

## 7. Verification

The flow under test was: localized home -> search/loading/results or recovery
state -> saved-book details -> localized public link and copy feedback.

The production frontend ran at `http://127.0.0.1:3048`, with its server-side
backend URL pointing to the controlled fixture at port 8047. Model/catalog keys
were blank for the frontend checks. Cover requests received placeholders;
clipboard writes were replaced with controlled success or denial inside each
isolated browser context. No operating-system clipboard was read or overwritten.

| Check actually performed | Result |
| --- | --- |
| Existing native frontend suite after the final source edit | **46 passed**, zero failures, cancellations or skips. |
| Frontend ESLint | Passed without disabled checks. |
| Production Next.js build and TypeScript | Passed; all nine static outputs generated and saved-book partial prerendering retained. |
| Main browser matrix | **190 of 190 scenario checks passed**, containing 910 individual assertions across 10 locale/viewport combinations. |
| Supplementary browser matrix | **20 of 20 scenario checks passed**, containing 84 assertions across both locales at 375px and 1280px. |
| Page identity, meaningful content and overlays | Expected routes/titles and visible content verified; no framework error overlay. Hidden retained routes were excluded from visible-heading counts. |
| Search states and recovery | Loading disables query/filters, exposes busy state and respects reduced motion; cancellation and six controlled failure modes restore focus and clear partial/stale cards. Normal five-book and limited three-book states, detail-link gating and long-token reflow passed. |
| Copy and detail states | Controlled success, delayed rejection, immediate repeated rejection and keyboard selection passed. Copied links exclude synthetic private query/fragment values. Missing-book and unavailable-book pages show localized safe feedback and the appropriate retry link. |
| Responsive rendering | Both locales passed at 1280x900, 375x812, 320x740, 844x390 with dark preference, and 375x812 with 200% root text and reduced motion. Both enlarged-text loading documents measured 375px, with a 32px root font. |
| Supplementary interactions | Enter submits all three selected filters and the correct locale; descriptions expand/collapse; store links retain HTTPS/new-tab protections; details locale switching retains ISBN; preference reload and explicit-locale precedence work; locale switching during an unfinished search clears query/busy/results and does not admit old cards after the fixture completes. Filter checks establish UI serialization, not live recommendation relevance. |
| Console and external requests | No page errors or relevant application warnings/errors in the main final matrix; no unexpected external-origin requests. Thirty exact `/api/search` resource notices were expected from the deliberately triggered HTTP 429/503 responses and retained separately. |
| Visual inspection | Inspected final desktop results, selected Spanish manual-copy fallback and enlarged-text loading screenshots. The visible controls and selected link support the DOM assertions; placeholder covers are explicitly fixture assets. |
| Retained acceptance evidence audit | Existing 20-case capture `eval-live-20261113-round25-merge-gate.json` verified against unchanged recommendation sources: 20 cases and 144 cards. This is file-only historical evidence, not a fresh live run or current usage reading. |
| Cleanup | Verified process ownership and stopped only the native test frontend/fixture trees. Ports 3048/8047 closed; original backend/PostgreSQL/Redis containers remained stopped and their volumes were not used. |
| Final submission review | Exact five-file scope and unchanged tested source/evidence hashes verified. English content, configured-secret matching, unwanted attribution and whitespace checks passed. Author/committer identities match the owner. Default and effective daily settings are 100, with no private-file override. Nothing was staged or uploaded. |

The final browser evidence is retained as `final3/report.json` and
`supplement/report.json` outside Git, together with screenshots, ARIA snapshots,
test/build logs, fixture traffic and LF-normalized source/evidence fingerprints
in `verified-source-manifest.json`. Final total: **210 scenario checks and 994
individual assertions**. These are controlled UI checks, not 210 live searches.

### Retained failures and harness corrections

- Initial baseline reports counted hidden Next.js retained headings as visible content. A separate corrected report uses visible headings; the original failure was kept and no route implementation changed to satisfy it.
- Baseline captures reproduced missing cancellation/error focus, unselected clipboard fallback, 14px link text and the enlarged-text overflow. Intermediate `final1` retained the real remaining 385px skeleton overflow, which led to the additional placeholder constraint.
- A Python escape in the temporary console classifier became a backspace rather than a regular-expression word boundary. The script was corrected to classify only the exact expected local search URL, message prefix and 429/503 status. Its original report still contains all 30 notices; general console errors were not suppressed.
- An intermediate diagnostic used an incorrect English button label and timed out; the corrected diagnostic used the actual localized control and measured the overflowing placeholders. An intermediate `final2` run stopped on a test-script UTF-8 decoding error in the Spanish language-button label. Explicit UTF-8 handling corrected the harness; the failed run was retained. The final full matrix kept the same UI expectations.
- An initial final-review assertion assumed the private environment file contained an explicit cap line. It contains no override. The corrected read-only review checks the application default and process/file overrides together, confirming 100 without changing configuration or opening the usage ledger.

No backend/integration tests were rerun because no backend code or persistence
behavior changed. No new real model/catalog, full 20-query live evaluation,
database, public ingress, real retailer/cover, social-platform, Safari, Firefox,
physical-device, native clipboard-permission or load test was performed. Mobile
checks use Chromium viewport emulation; the 200% test is text enlargement, not a
claim about every browser zoom mode. The historical cap/usage values in the
acceptance audit belong to its original capture and do not describe today's
allowance. No new latency or public-release guarantee follows from this round.

## 8. Approvals and remaining work

The user's request to continue to the next round authorizes this routine MVP
interface verification and the reproduced, reversible fixes. No major technical
decision was required. No paid service, public host, release or deployment was
created. All new repository explanation is English; existing intentional Spanish
interface/catalog content remains.

No reproduced defect remains open within the tested UI matrix. Existing broader
limits remain: streamed detail errors can return HTTP 200; actual public sharing
and social-platform caching need a reachable approved deployment; recommendation
metadata/lexical checks do not establish every semantic reading constraint.
Cross-browser/device checks and production ingress/recovery verification remain
outside this local round.

The next planned closeout area is deployment preparation using the existing
proposal, followed by operational recovery and final acceptance/documentation.
Host/domain/budget, backup destination/schedule/retention and first public
activation still require their corresponding concrete approvals. This plan is
not a claim that the project is already publicly released or that remaining
work is a guaranteed fixed number of rounds.

## 9. GitHub submission

**Proposed commit title:** `fix: restore keyboard recovery and mobile control reflow`

**Proposed commit description:**

Search cancellation or failure could leave focus on the document, clipboard
denial required another navigation step to select the public link, and enlarged
loading controls/placeholders could create horizontal scrolling. Restore focus
to the enabled request field after failure/cancellation, focus and select the
manual-copy fallback including immediate retries, and use the base link font.
Allow the search/cancel group to wrap and bound the loading placeholder to its
column. Document the behavior and correct the stale README preview exclusion.

Verification: 46 existing frontend tests, ESLint and the production
Next.js/TypeScript build passed. Controlled Chromium verification passed 190 main
and 20 supplementary scenario checks in English/Spanish, including desktop,
narrow/mobile, landscape and 200% text, keyboard recovery, copy outcomes,
filter submission, preference persistence and stale-result prevention. Preserve
failed intermediate captures and explain harness corrections. The unchanged
historical 20-case recommendation capture also passed its file-only audit.

No backend API/schema, model/prompt/retrieval, dependency, provider, deployment or
daily-policy change. No new real model/catalog/database calls or public-platform
tests occurred. The UI edits are reversible without data migration. See
`update_version/Lumen_Update_Version_28.md` for scope, evidence, compatibility and
remaining deployment/cross-browser work. This round depends on the separately
reviewed, local-only round-27 commit `a48b1f7`.

**Status at local checkpoint preparation:** after implementation, the user
requested merging main and starting the next round, with questions before
unresolved decisions. The five reviewed round-28 files are being saved in a
local-only checkpoint. A fresh remote fetch confirms main still at `c2ae919`.
The merge also contains the ten-file round-27 dependency, which has not been
uploaded. The combined review contains fourteen distinct files because both
rounds modify the README. Round-specific upload confirmation is being obtained
for the dependent scope before any push. No push, pull request, merge, release
or deployment has occurred at this checkpoint. A later update record will
identify the actual commit and any subsequently authorized upload/main checks;
permission for older rounds does not publish these changes.
