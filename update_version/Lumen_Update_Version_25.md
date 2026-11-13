# Lumen Update Version 25

## 1. Basic information

- **Round:** 25; an implementation round, not an application release.
- **Dates:** 2026-11-12 through 2026-11-13, Europe/Madrid.
- **Branch:** `codex/update-25-reading-intent-and-latency`.
- **Known baseline:** `d5642f303ff2d3fe8bd1a1d45cfd3522b3f08db6`, round 24 on local and remote `main`.
- **Objective:** fix demonstrated reading-form and reason-check failures, publisher-only grounding, first-card latency and misleading failed-evaluation diagnostics, then verify within the explicitly approved temporary acceptance ceilings.
- **Actual scope:** original-request validation at ranking, stream, persistence/cache and evaluation boundaries; catalog form/subgenre retrieval, bounded description enrichment, concise incremental ranking, first-card lookup deadlines, truthful HTTP/partial-result evidence, runtime diagnostics, regressions and retained live captures. Prompts and retrieval changed. Model/catalog providers, dependencies, graph topology, database schema and public API/SSE fields did not change. The default daily cap remains 100; the temporary acceptance exception is documented below.

### Round-24 merge receipt

The user explicitly confirmed uploading the reviewed 11-file round-24 branch and
synchronizing remote `main` after hosted checks. The scope and owner identity
were reverified, the confirmation was appended to the existing round record,
and commit `d5642f303ff2d3fe8bd1a1d45cfd3522b3f08db6` was created with the full
reviewed description. The branch was uploaded; all three [branch jobs](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43313386582)
passed. Local `main` was fast-forwarded, remote `main` was pushed to the same
commit without rewriting history, and all three [main jobs](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43314346634)
passed. The next branch was based on that exact commit; the pending round-25
changes are separate and have not been uploaded. Round 24 preserved its three
live latency failures and semantic findings; its merge did not establish release
readiness or waive the live gate for these later behavioral corrections.

## 2. Technologies used

No dependency or paid service was added. Existing Python regular expressions
and accent-normalized catalog text implement deliberately conservative type
checks. Existing LangGraph state retains the original request genre through
broadenings; Pydantic models, candidate ISBN checks and SQLAlchemy persistence
guards continue to enforce the existing boundary. Existing FastAPI SSE and
HTTPX/`asyncio.timeout` bound optional enrichment without changing the wire
contract. Pytest, scripted model doubles and HTTPX mock transport reproduce the
actual bad-book and stalled-lookup patterns. PostgreSQL 17, Redis 7, Alembic and
Ruff provide isolated integration, migration and style checks. The existing
Next.js production build supplies the actual local frontend proxy; no frontend
source was changed or new frontend build claimed for this round.

## 3. November 12 implementation checkpoint

Sections 3 and 5 through 8 preserve the initial checkpoint. Section 4 lists the
current complete file scope. Sections 9 and 10 describe the final submission
proposal and November 13 follow-up, including current verification and limits.

### Reproduction and causes

Before changing production code, eight focused offline regressions failed in
3.47 seconds: six real catalog snapshots incorrectly passed reading-form
validation, an actual direct history-versus-fiction concession passed final pick
validation, and a blocked optional store HTTP transport prevented first-book
receipt. The retained command was the two new regression files run with pytest;
the private log is `backups/round25-red.log`. The book snapshots came only from
the existing public round-24 report, without live requests or invented ISBNs.

The causes were distinct: the reader-type guard previously recognized language
courses only; concession detection relied on forms such as "although" and missed
direct admissions; the first stream card awaited its optional store lookup with
the normal provider timeout. Ranked hypotheses and a red-capable loop preceded
the fixes. Additional boundary checks initially exposed overbroad interpretation
of novel-history requests and ordinary plot negation; those failures were kept
while the implementation was corrected rather than weakening the assertions.

### Preserve the original reading form

`matches_reader_type` now recognizes fictional reading intent from the primary
request phrase and retained genre. Explicit UI genre takes precedence over an
inconsistent parsed genre and remains fixed through broadening. Clear coloring
or activity books, nonfiction/report forms and literary criticism do not satisfy
a fictional reading request. Explicit fictional catalog classification or a
clear opening description of the book as a novel avoids rejecting ordinary
historical fiction merely because its title contains a history-related word.
Nonfiction/criticism requests and ambiguous metadata remain eligible. The
existing language-practice exception and course rejection remain available.

The same predicate excludes clear mismatches before ranking and revalidates
selected candidates before streaming and persistence. Complete cached results
go through the existing repository validation, so a rewritten reason or a
tampered snapshot cannot bypass the requirement. The evaluator flags wrong form
under its existing reason check while keeping ISBN authenticity independent.
The six-check suite, normal/niche counts and candidate-membership rules remain.

Direct English and Spanish book-type concessions now include ordinary copular
admissions, contractions and explicit statements that a book does not match a
fiction filter. Only the missing requirement portion is compared with original
request terms, with known literary-form aliases and irrelevant function words
removed. Positive "not only" statements and ordinary plot negation remain valid;
a nonfiction request can truthfully describe a book as not being a novel.
Previously rejected concession ISBNs retain the existing exclusion behavior.
This is a lexical/metadata safeguard, not a general semantic classifier.

### Bound the first card's optional lookup

`BookCardBuilder.build` accepts an internal optional lookup timeout; its default
preserves the existing behavior for other callers. The stream supplies at most
one second for its first uncached card, reduced to the remaining 15-second
first-book budget minus 250 ms. The bound includes provider-lock and rate-spacing
waits. If no time remains, optional work is not started. Static validated ISBN
search links stay available. Fast successful optional links are retained.

Timed-out work is cancelled and recorded as `unavailable`, never cached as an
authoritative `not_found`. Provider locks are released, later attempts still
observe the original Apple request spacing, and outer/client cancellation is
not swallowed. There is no new background work or later link-update event.
Subsequent cards retain the existing enrichment behavior under the overall
60-second stream deadline. A graph that is already slow can still miss the
15-second first-book requirement; this change does not claim otherwise.

### Historical evidence and persistence

Offline replay of the unchanged round-24 capture now rejects wrong form/reason
evidence in four cases: `en_fantasy`, `en_classics`, `en_history` and `en_sea`.
Eight individual selections are flagged, including the six manually documented
examples. All twenty saved cases remain independently recheckable. The replay
records zero real calls and no new latency; it is not a passing live gate.

The existing integration test of a historical round-10 capture initially failed
because its `en_history` entry contains five direct concessions that the newer
validator correctly rejects. The source capture was not modified. The test now
explicitly identifies those five ISBNs, asserts that this one entire search is
rejected without changing database row counts, and still persists and reads the
other nineteen searches with real foreign keys. It does not derive an arbitrary
skip list from the current implementation or silently drop invalid picks.

## 4. Current complete file scope

The current round contains **49 modified/added public files**. The initial
November 12 checkpoint covered 17; the table includes the subsequent corrections
on the same branch. No file was deleted and no historical capture was overwritten.
Ignored private helpers, logs, JUnit evidence, archives, backups and temporary
configuration are outside this submission.

| File | Actual before/after purpose |
| --- | --- |
| `backend/app/book_cards.py` | Modified: add an optional bounded first-card lookup; preserve default later-card behavior, static links and cancellation. |
| `backend/app/filters.py` | Modified: carry narrative form and explicit superhero subgenre into catalog queries; preserve nonfiction, manga and short-story coverage exceptions. |
| `backend/app/graph/broaden.py` | Modified: preserve requested narrative form and core subject/setting in widened searches instead of substituting commentary. |
| `backend/app/graph/parse_query.py` | Modified: retain the requested reading form and subject in initial catalog searches. |
| `backend/app/graph/rank.py` | Modified: exclude wrong forms/boilerplate; request only new short explanations, retain validated picks and skip redundant ranks under the unchanged 30-book ceiling. |
| `backend/app/graph/search.py` | Modified: pass original genre to both catalogs and request 40 supported narrative Google records in the same HTTP request. |
| `backend/app/graph/workflow.py` | Modified: preserve original UI genre; add sparse graphic-retry work enrichment with priority, provenance and bounded lookups; pass retained picks to ranking. |
| `backend/app/grounding.py` | Modified: project usable synopsis evidence by decoding/stripping markup and publisher/copyright tails without mutating raw catalog descriptions. |
| `backend/app/reading_intent.py` | Modified: extend course-only rejection to demonstrated wrong forms, direct/catalog concessions, travel/criticism cues and combined superhero-graphic evidence; preserve positive controls. |
| `backend/app/repository.py` | Modified: revalidate original reading form before persistence and completed-cache reuse; refuse incomplete or unsupported snapshots atomically. |
| `backend/app/search_stream.py` | Modified: revalidate type and bound the first uncached optional lookup to remaining first-book time; preserve the SSE contract. |
| `backend/app/sources/descriptions.py` | Modified: permit verified work evidence to replace missing or publisher-only descriptions; preserve original work payload and identity checks. |
| `backend/app/sources/google_books.py` | Modified: accept optional original filters and apply catalog query constraints; preserve legacy default result count for direct callers. |
| `backend/app/sources/open_library.py` | Modified: apply original form/subgenre alongside existing language, year and page constraints. |
| `backend/evals/README.md` | Modified: document real grounding/type checks, bounded enrichment, diagnostic truthfulness, coverage exceptions and temporary-policy rules. |
| `backend/evals/checks.py` | Modified: use the same usable description and original reading-form/concession validation in the existing reason check. |
| `backend/evals/http_run.py` | Modified: preserve safe allowlisted HTTP errors and actual wire recommendations; retain interim selections only as audit evidence; block interrupted checks while failing healthy empty counts. |
| `backend/evals/results/eval-live-20261112-round25-reading-form.json` | Added: complete 20-request real frontend capture retaining all actual failures, quota/cache evidence and source fingerprints; gate not passed. |
| `backend/evals/results/eval-live-20261112-round25-review.md` | Added: initial latency, interrupted delivery and semantic false-negative findings, without rewriting the source capture. |
| `backend/evals/results/eval-live-20261113-round25-merge-gate.json` | Added: final source-matched complete 20-case real frontend capture; all six checks satisfied, 44 shared attempts and cache evidence retained. |
| `backend/evals/results/eval-live-20261113-round25-final.json` | Added: complete 20-request real frontend capture retaining all actual failures, quota/cache evidence and source fingerprints; gate not passed. |
| `backend/evals/results/eval-live-20261113-round25-followup.json` | Added: complete 20-request real frontend capture retaining all actual failures, quota/cache evidence and source fingerprints; gate not passed. |
| `backend/evals/results/eval-live-20261113-round25-review.md` | Added: complete follow-up capture/probe chronology, manual false positives, budget accounting and remaining full-gate requirement. |
| `backend/evals/results/eval-live-20261113-round25-subjects.json` | Added: complete 20-request real frontend capture retaining all actual failures, quota/cache evidence and source fingerprints; gate not passed. |
| `backend/evals/results/eval-supplementary-20261113-round25-comics-current.json` | Added: single-case real frontend capture, 7 cards, first 7,568.05 ms, shared use 188 to 190; explicitly not a full gate. |
| `backend/evals/results/eval-supplementary-20261113-round25-comics-enriched.json` | Added: single-case real frontend capture, 6 cards, first 10,256.51 ms, shared use 177 to 181; explicitly not a full gate. |
| `backend/evals/results/eval-supplementary-20261113-round25-comics-evidence.json` | Added: single-case real frontend capture, 2 cards, first 10,054.48 ms, shared use 181 to 186; explicitly not a full gate. |
| `backend/evals/results/eval-supplementary-20261113-round25-comics.json` | Added: single-case real frontend capture, 4 cards, first 11,972.15 ms, shared use 171 to 177; explicitly not a full gate. |
| `backend/evals/results/eval-supplementary-20261113-round25-superhero-subject.json` | Added: single-case real frontend capture, 8 cards, first 7,505.93 ms, shared use 186 to 188; explicitly not a full gate. |
| `backend/evals/results/reading-form-replay-20261112-round25.json` | Added: offline recheck of all 20 retained cases with current non-latency validation; zero live calls and no new timing/gate claim. |
| `backend/evals/results/reading-form-replay-20261113-round25-current.json` | Added: offline recheck of all 20 retained cases with current non-latency validation; zero live calls and no new timing/gate claim. |
| `backend/evals/results/reading-form-replay-20261113-round25-followup.json` | Added: offline recheck of all 20 retained cases with current non-latency validation; zero live calls and no new timing/gate claim. |
| `backend/integration_tests/test_daily_budget.py` | Modified: verify temporary 200/300 and normal 100 policies share one irreversible usage floor and concurrent reservations stop exactly at the cap. |
| `backend/integration_tests/test_replay_and_stream.py` | Modified: explicitly reject three known historical evidence-incompatible searches without writes; retain 17 valid real-FK round trips. |
| `backend/integration_tests/test_runtime_readiness.py` | Modified: require explicit declared temporary 200/300 expectations and prove diagnostics do not mutate the ledger or cache keys. |
| `backend/scripts/check_runtime_readiness.py` | Modified: accept an explicit 100/200/300 expected-cap diagnostic argument; keep default 100 and read-only behavior. |
| `backend/tests/fixtures/reading_type_followup_update25.json` | Added: original catalog snapshots for four commentary/expedition failures and one publisher-only description. |
| `backend/tests/fixtures/reading_type_mismatches_update24.json` | Added: six actual round-24 catalog/reason failures; no invented bibliographic identities. |
| `backend/tests/fixtures/travel_mismatches_update25.json` | Added: three actual travel-guide/writing substitutions for novel requests. |
| `backend/tests/test_author_constraints.py` | Modified: align scripted outputs with skipped redundant ranking while retaining original author constraints and bounded-flow assertions. |
| `backend/tests/test_catalog_subjects.py` | Added: regression coverage for catalog forms, exact superhero subject, exclusions, manga/collection coverage and 40-record retrieval without extra HTTP requests. |
| `backend/tests/test_descriptions.py` | Modified: prove verified work evidence can replace copyright-only text without changing original input evidence. |
| `backend/tests/test_first_card_lookup_deadline.py` | Added: stalled transport, fast result, deadline cleanup, spacing, retry and outer-cancellation regressions. |
| `backend/tests/test_http_eval_failures.py` | Added: real loopback mocked HTTP regressions for safe 503 codes, private/oversized bodies, undelivered interim picks and healthy empty count failures. |
| `backend/tests/test_reading_form_followup.py` | Added: real commentary/expedition/travel/boilerplate examples, positive fiction/nonfiction controls, catalog concessions and combined graphic subject evidence. |
| `backend/tests/test_reading_type_regressions.py` | Added: actual round-24 mismatch snapshots through ranking, evaluator, workflow, persistence/cache and bilingual boundary seams. |
| `backend/tests/test_workflow.py` | Modified: test sparse graphic enrichment, priority/provenance/global bounds and retained picks; preserve fixed retries and real HTTP-source failure coverage. |
| `docs/live-acceptance.md` | Modified: document first-card deadline, process-only temporary 200 policy, no-refund restoration and source-matched full-gate requirements. |
| `update_version/Lumen_Update_Version_25.md` | Added: coherent round history, current implementation/file scope, approvals, actual verification, submission proposal and remaining work. |

## 5. Initial project benefits

Catalog authenticity can no longer by itself justify the demonstrated coloring,
report and criticism substitutions for requested novels. A model cannot keep a
clear mismatch simply by rewriting its reason. Preserving a reader-selected
genre prevents the first parse or later broadening from replacing it. Optional
store availability can no longer consume an unbounded portion of first-card
delivery, while its absence remains truthful. Regression tests exercise the
real ranking, cache/persistence, evaluator and stream seams rather than only
checking newly added helper outputs.

## 6. Initial future impact and compatibility

The public API and SSE schema/event order, database schema/migrations, providers,
dependency lock, daily allowance, graph limits and product scope are unchanged.
The code signature changes effective parse/result cache namespaces as already
designed; deploying may require cold work under the unchanged shared cap.
Existing cache keys, stored books/searches and allowance are not deleted/reset.

Validation is deliberately stricter: historical/tampered complete snapshots with
the demonstrated wrong forms or concessions can now be refused. Previously
persisted rows are not migrated or erased; this is a write/replay guard. The
first card may omit a slow optional Apple link that would have arrived later,
while keeping existing ISBN search links and recording unavailability. This is
a bounded optional failure path, not a claim that the store lacks the book.
Default builder callers and subsequent streamed cards retain prior behavior.

These heuristics can still miss subtle genre, mood, setting, nationality and
audience mismatches or encounter conflicting metadata. Fewer accepted candidates
can increase broadening work and produce valid small subsets or count failures;
normal searches still require 5–10 in acceptance. No retry/call limit is raised
to compensate. Public release remains dependent on a full passing live gate and
the separate approved host/domain/deployment work.

## 7. November 12 verification checkpoint

| Check actually performed | Result |
| --- | --- |
| Pre-fix real-snapshot/stalled-transport reproduction | Eight failures in 3.47 seconds, retained privately. The exact bug seams later passed. |
| Boundary checks during implementation | Initial failures exposed overbroad forms/negation; corrected code retained the expectations. |
| Native complete offline suite | **458 passed** in 5.49 seconds with blank keys and unusable service endpoints. |
| Initial isolated Linux full run | Lint/format, migration/model checks and 458 offline tests passed. Integration had 75 passes and one historical unconditional-save failure, retained in its original logs. |
| Final isolated Linux lint/format | Passed; 119 Python files already formatted. The transient explicit-string-concatenation lint errors were corrected without disabling checks. |
| Final isolated Linux offline suite | **458 passed** in 4.12 seconds. |
| Final real isolated PostgreSQL/Redis suite | **76 passed** in 10.87 seconds, including the explicit historical rejection and nineteen valid FK round trips. **534 distinct backend tests** passed; native repetition is not counted twice. |
| Fresh schema migrations/model agreement | Passed on the disposable database. |
| Offline recheck of original 20-case round-24 report | Four reason-check cases failed as intended, eight old selections flagged. Other non-latency checks retained 20/20 passes. Eighteen timings blocked and two inapplicable; no live calls or new timing evidence. |
| Remote round-24 branch/main checks | Three jobs passed for each event, linked above. These are not round-25 hosted results. |
| Original-ledger pre-run readiness | Migration marker matched, services usable, known 54/100 UTC-day usage; no model/catalog calls. |
| Fresh private original-database backup/recovery | Verified matching fingerprints for 1,385 books, 94 searches, 522 results, one migration marker and one ledger row. Source unchanged; recovered copy blocked. |
| Authorized real frontend acceptance | All 20 HTTP requests completed, but **gate not passed**, exit 1. Fifteen responses were HTTP 200; one of those searches was interrupted by the daily guard. The remaining five were HTTP 503 after exhaustion, not successful empty recommendations. |
| Shared accounting | Budget changed from **54 to 100/100** for UTC 2026-11-12, exactly the authorized 46 remaining attempts. Per-search diagnostics totaled 46 reserved attempts and 47 logical calls; the final denied logical invocation reserved/sent no extra attempt. Maximum observed logical calls per case was six and broadenings two. No independent allowance or refund was created. |
| Live six-check summary | Authenticity/language/reason: 15 pass, 5 blocked each. Count/links: 14 pass, 1 fail, 5 blocked each. Latency: 11 pass, 2 fail, 1 inapplicable, 6 blocked. Passes on partial captured state do not override the search error or establish complete product success. |
| Live cache evidence | Fifteen captured flags were false; five admission-denied cases had null evidence. Parsing/catalog caches remained shared and are not fully tracked. No fully cold-cache claim is made. |
| Manual review | Further philosophical commentary, an essay about comics and an expedition account still passed the conservative form heuristic. Four specific examples/ISBNs are retained in the new review; they remain release-blocking. |
| Final local readiness | Read-only diagnostic reported `cached_only`, known **100/100** exhausted allowance, healthy PostgreSQL/Redis and matching migration marker. Eligible cache reuse is possible in principle; no new uncached work is authorized by this state. |
| Content and evaluated-source review | No configured key/long private database-password matches, unwanted attribution or Chinese explanatory text in the 17-file scope; Spanish fixtures and original catalog text are intentional. All live application/evaluation source fingerprints matched the final code. |
| Cleanup | Both regression runs removed owned resources. The live backend stopped, temporary loopback data containers/network and the exact native frontend process tree were removed. Original containers remained stopped and original data volumes were verified preserved with the 100-attempt floor intact. |

Both isolated regression runs cleaned up their owned resources. The native
frontend reused the unchanged verified production build and targets the new
evaluation backend on loopback. There is no new frontend build, public Caddy,
DNS/TLS, browser-layout, production-load or deployment claim. Store URL templates
were not changed or re-probed; earlier bounded header reachability does not
establish current product availability or stock. No second live run occurred in the November 12 window.

### Actual unsuccessful cases

| Case | Actual result and limitation |
| --- | --- |
| `en_short_modern` | First book **16,502.65 ms**, above 15,000 ms after the bounded workflow. |
| `en_sea` | First book **15,076.13 ms**, above 15,000 ms; the threshold was not rounded upward. |
| `es_classics` | The daily guard stopped the next logical invocation after usage reached 100. Four interim graph picks were retained as partial evidence, but zero cards were streamed and `rate_limited` was emitted. Count and links failed; latency was blocked. This is not a successful four-book result or a newly broken store template. |
| `es_science`, `es_history`, `es_sea`, `es_niche`, `es_nonsense` | The existing known-exhaustion admission path returned HTTP 503. All checks were blocked, including nonsense, rather than treating missing output as an intended empty response. |

The capture contains 97 actual wire cards from thirteen nonempty successful
streams plus one successful nonsense stream. The two latency failures remain
failures even when other checks pass. The manual semantic review demonstrates
that the automated reason/type rule still has false negatives. Real usage never
exceeded the authorized shared daily total, and service cleanup did not restore
or lower that total.

## 8. November 12 approvals and remaining work checkpoint

No major architecture, schema, provider, core-capability, spending-limit or
scope decision was required; these are corrections within the approved reading
requirements and optional-channel failure behavior. The user explicitly
confirmed round-24 upload/main synchronization. For round 25, the user separately
authorized the 20-case real verification, consuming at most the original
remaining 46 attempts for UTC 2026-11-12. Before the run the real shared ledger
was read as 54/100, and all older original containers remained stopped. There is
no initialization, clone allowance, reset, refund, raised cap or unlimited retry
authorization. The standard guard must deny work if the day becomes exhausted.

The initial eight-failure reproduction and all boundary/integration failures
are explained above. No unsuccessful run was renamed a success or replaced.
Keep the strengthened constraints even if they reduce counts. Full new live
acceptance remains required before merging these behavior changes; the offline
replay cannot replace it. Any unverified semantic relevance or public-release
requirements remain explicit follow-up work. Round-25 upload is not authorized
by either the previous merge or this bounded call approval.

The remaining implementation work is more varied book-form recognition using
the new commentary/essay/expedition counterexamples, with positive historical
and graphic-fiction controls; additional investigation of the sequential
parse/search/broaden/rank timing; and a new complete passing real gate after
correction with known available allowance and explicit real-call authorization.
The current report is not passing, so this round must not be merged as a verified
recommendation fix. Waiting for natural UTC rollover is different from resetting
the ledger; no scheduled continuation, allowance change or further live request
was performed. Public deployment, active backup scheduling and host/domain
choices also remain separate pending work.

## 9. Current GitHub submission proposal

**Proposed commit title:** `fix: ground reading forms and improve bounded search acceptance`

**Proposed commit description:**

Reject demonstrated activity-book, commentary, essay, expedition and travel
substitutes at ranking, stream, persistence/cache and evaluation boundaries.
Preserve original UI genre and explicit author constraints through the fixed
flow. Strip publisher/copyright boilerplate from grounding evidence while
retaining original bibliographic payloads. Recognize direct bilingual and
catalog-text concessions, preserving ordinary plot negation and requested
nonfiction. Explicit superhero-graphic requests need evidence for both form and
subject, with conservative limits documented.

Carry narrative form and explicit superhero subgenre into the existing catalog
queries, expand supported Google Books retrieval to 40 records per request, and
retain the 30-book ranking ceiling. Preserve manga/short-story coverage
exceptions. Add bounded verified work-description enrichment on sparse graphic
retries and retain its provenance. Ask only for new short explanations while
retaining validated picks; preserve both broadenings and all logical-call limits.
Bound the first card's optional lookup without negative caching or wire changes.

Make HTTP evaluation retain allowlisted error codes and actual delivered cards;
keep interim graph selections only as audit evidence and block interrupted
checks. Healthy empty ordinary searches still fail count. Permit an explicitly
declared temporary 200/300-cap readiness expectation without mutating the singleton
or changing the default 100 policy. Add real-snapshot, workflow, deadline,
accounting and failure-diagnostic regressions. Preserve every unsuccessful
capture. No provider, dependency, API/SSE schema or database migration changes.

Validation: 503 unit and 81 PostgreSQL/Redis integration tests passed (584
distinct), plus lint/format, fresh migrations and model agreement. The complete
20-case real frontend gate passed: authenticity, language, count, links and
reason each 20/20; latency 18 passes and two intended nonsense exceptions, with
maximum first-book delivery 9,701.89 ms. It used 44 actual attempts, sharing the
original count from 190 to 234 under the separately approved temporary 300 cap.
One complete-result hit is disclosed; no fully cold-run claim is made. Earlier
failed captures and source-matched supplementary probes remain unchanged. The
default cap was restored to 100 without lowering use. See
`update_version/Lumen_Update_Version_25.md` and
`backend/evals/results/eval-live-20261113-round25-review.md` for evidence,
compatibility, stricter metadata limitations and release boundaries.

**Status at commit preparation:** the user explicitly authorized this reviewed
round's upload and synchronization of `main`, then separately approved the
300-cap acceptance continuation on the same 190-attempt floor. The complete live
gate and local checks now pass. The 49-file scope is ready to commit/upload;
remote checks and main synchronization have not yet occurred at this snapshot.
They must succeed before starting the next implementation round. The subsequent
commit, hosted-check and merge receipts will be recorded in that next round's
update record rather than claiming a future result here.

Git author and committer were verified as
`ZhiouZhu2001 <zhiouzhu2001@gmail.com>`. No pull request, release, deployment,
collaborator change or attribution is authorized or added. Earlier round-24
hosted receipts are independent evidence.

## 10. November 13 correction and verification follow-up

### Authorization, baseline and preserved data

The user requested correction of the known defects and explicitly authorized a
**temporary 200-attempt ceiling**. This is the only spending-policy exception;
no higher limit was assumed. The earlier approval-service usage outage prevented
execution at that moment; it was reported and no alternative allowance was
created. After the user said to continue, the original working-tree fingerprints
and round-25 branch/baseline were checked before corrections. The unfinished
round stayed on its existing coherent branch; no earlier changes were claimed
as a separate new round.

The existing stopped original database/Redis volumes were mounted by temporary
loopback-only services, with original application workers kept stopped. The
pre-run verified backup contained 1,891 books, 108 searches, 619 results, one
migration marker and one budget row. Recovery fingerprints matched, source data
was unchanged, and the recovered copy remained blocked. The PostgreSQL UTC day
naturally changed to 2026-11-13 with zero current-day use; the preceding day's
100-attempt floor was not manually reset, refunded or edited.

Only the evaluation backend process used `DAILY_AI_CALL_CAP=200`. Normal settings
and `.env` retained 100. Readiness now accepts an explicit
`--expected-daily-cap 200` comparison; its default remains 100 and the diagnostic
is read-only. A real integration test reserves from the same singleton under
200, restores 100 without lowering use, and proves concurrent callers cannot
exceed 200. An hourly evaluation namespace changes IP admission keys only.

### Additional causes and implementation

- **More reading-form evidence:** recorded philosophical commentary, essays,
  expedition accounts, travel guides and travel writing were accepted by the
  initial lexical check. Strong self-descriptions and explicit travel metadata
  now reject them for requested narratives. Genuine historical/philosophical/
  travel novels and explicitly requested nonfiction remain valid controls.
  Critical compilations do not become graphic fiction solely because a catalog
  category contains comics.
- **Grounding projection:** HTML and escaped HTML are decoded/stripped before
  locating known publisher, copyright and preservation boilerplate. Only usable
  book-specific text reaches ranking/reason grounding. Original descriptions
  and provider payloads remain unchanged; Unicode offsets are preserved when
  cutting the original text. Boilerplate alone cannot make a book rankable.
- **Retrieval coverage:** original genre reaches both existing catalog clients,
  including unconstrained requests. Narrative forms use compatible subject
  fields; superhero comics use `subject:superheroes` rather than only comics.
  Literal superhero anchoring preserves the original subgenre without inventing
  names; exclusions/comparisons do not become positive requirements. Supported
  narrative Google requests fetch 40 records rather than 20 without adding a
  request. The model still sees at most 30. Nonfiction and short-story collections
  retain coverage, while manga retains its literal form without the overstrict
  generic comics tag that failed a real run.
- **Sparse graphic metadata:** after a broadening with fewer than five retained
  picks, at most three missing/publisher-only Open Library work descriptions are
  attempted per retry, under the existing eight-work global ceiling, concurrency
  of three and two-second individual timeout. Supported form/subject evidence
  gets priority; repeated work keys are not retried. Response keys must match
  validated work keys. Normalized description, original work payload and earliest
  catalog timestamp are retained; no synthetic ISBN or synopsis is introduced.
  Year/page-constrained searches retain their existing eight-work behavior.
- **Explicit combined graphic requirement:** superhero-graphic requests require
  evidence for both form and subject in catalog title/categories/usable synopsis
  before selection and at final validation. Enrichment can inspect missing
  descriptions first but cannot bypass final validation. Other ambiguous forms
  remain under the conservative rule. This can refuse genuine comics when their
  captured metadata lacks proof; it does not prove every mood or moral theme.
- **Bounded latency:** rank output asks for two short sentences, roughly 20–35
  words total, meeting the specification's sentence range. Already validated
  explanations are retained, and later ranking asks only for additional picks.
  A redundant rank call is skipped when no usable unretained candidate exists;
  the fixed graph and two broadenings still execute as applicable. The maximum
  remains six logical invocations. No model/provider/reasoning-mode change was
  made; the first-card optional deadline from November 12 remains.
- **Truthful diagnostics:** HTTP failure bodies are read only within 8,192 bytes;
  known error codes are allowlisted without echoing private error text. Actual
  streamed cards define delivered recommendations. Interim graph picks are kept
  separately for an interrupted search; all six interrupted checks are blocked.
  A normally completed empty ordinary search still fails count, while intended
  nonsense emptiness retains its existing behavior. Catalog-text concessions in
  English/Spanish now reject explicit admissions that requested themes are absent.

No new dependency or technology was introduced. All mechanisms use the existing
Python/Pydantic, LangGraph, HTTPX, catalog APIs, FastAPI/Next proxy, PostgreSQL,
Redis, Alembic, Docker, Ruff and pytest stack. Database foreign keys, author
matching, language checks, two-retry bound, privacy protections and no-refund
accounting remain in force. Broadening output does not override original genre.

### Reproduction and verification actually performed

The follow-up initially reproduced seven failures in the new fixture/diagnostic
seams. Subsequent red tests separately caught overrestrictive catalog subjects,
travel-form leakage, manga coverage loss, healthy-empty result misclassification,
20-versus-40 retrieval, missing work enrichment, catalog concessions, mixed
form/subject substitutions, enrichment order and the generic superhero subject.
Logs are retained under ignored `backups/round25-*.log`; failures were corrected
without bypassing assertions, changing the suite or relaxing the thresholds.
Windows fixture reads were made explicitly UTF-8. Scripted-model responses were
updated to model the genuinely skipped redundant ranks, retaining call/retry
assertions.

Historical replay is deliberately stricter. The unchanged round-10 capture now
has three explicitly enumerated searches that cannot be written atomically:
`en_history` contains five direct concessions, `es_niche` contains two travel
substitutions, and `en_comics` has two real comics whose old snapshot lacks the
new combined evidence. The latter are not claimed to be counterfeit or actually
wrong-form books. Their ISBNs are `9781401220341` and `9781401288228`. The other
17 searches are still persisted and read with real foreign keys. An intermediate
run failed this assertion before the known evidence limitation was reviewed and
explicitly documented; no dynamically derived skip list was introduced.

| Verification | Actual result |
| --- | --- |
| Native complete offline suite before final compatibility scoping | 503 passed in 16.21 s, keys blank; no real model/catalog calls. |
| Final isolated Linux lint/format | Passed with no checks disabled. |
| Final isolated unit suite | **503 passed**, zero errors/failures/skips. |
| Final real isolated PostgreSQL/Redis suite | **79 passed**, zero errors/failures/skips; **582 distinct backend tests** total. |
| Fresh Alembic upgrade and model agreement | Passed on a disposable database; no migration added. |
| Final isolated source archive | `backups/lumen-round25-regression-00718e7c6d/source.tar`, SHA-256 `fcf757aa9893cd925b67b6de6625c6646f2072e8f8f9fb6ac40a33e8c1e24d24`; owned resources removed. |
| New full real frontend captures | Three complete 20-case runs; all failed at least one check. See the retained review/table below. |
| Final current-source real comics probe | Seven books, first book **7,568.05 ms**, all six automated single-case checks passed; two logical calls/two attempts, no broadening. **Not a full gate.** |
| Current offline replay of latest full capture | Twenty cases rechecked without services; four old English-comics selections flagged. Count 19 pass/1 fail; reason 19 pass/1 fail. Eighteen timings blocked, two inapplicable. |
| Final public content/source review and cleanup | Recorded after the bounded window closes; see the closing receipt below. |

The full/probe sequence on the **same** UTC-day ledger is retained separately:

| Report suffix, all under `backend/evals/results/` | Attempts before/after | Actual result |
| --- | --- | --- |
| `eval-live-20261113-round25-followup.json` | 0 / 62 | Full 20; Spanish history count three; all 18 applicable latencies pass, two inapplicable; gate false; manual travel mismatches. |
| `eval-live-20261113-round25-subjects.json` | 62 / 117 | Full 20; Spanish manga empty due to overrestrictive subject; 19 cases pass, one blocked by that evaluator revision; gate false. |
| `eval-live-20261113-round25-final.json` | 117 / 171 | Full 20; English comics count four; all 18 applicable latencies pass; other five checks 20 pass; gate false. Filename predates later fixes. |
| `eval-supplementary-20261113-round25-comics.json` | 171 / 177 | Single case; four books; first 11,972 ms; count failed. |
| `eval-supplementary-20261113-round25-comics-enriched.json` | 177 / 181 | Single case; six books; first 10,257 ms; automatic checks pass, manual form/theme false positives remain. |
| `eval-supplementary-20261113-round25-comics-evidence.json` | 181 / 186 | Single case; two books; first 10,054 ms; count failed after stricter evidence. |
| `eval-supplementary-20261113-round25-superhero-subject.json` | 186 / 188 | Single case; eight books; first 7,506 ms; all single-case checks pass. |
| `eval-supplementary-20261113-round25-comics-current.json` | 188 / 190 | Current-source single case; seven books; first 7,568 ms; all single-case checks pass. |

The new manual review is `backend/evals/results/eval-live-20261113-round25-review.md`.
All unsuccessful evidence remains unchanged. Supplementary reports explicitly
say `full_suite: false` and `gate_passed: false`; none is renamed a complete
success. Current snapshots show real form/subject evidence, while thematic fit
and factual entailment remain heuristic. The existing frontend production build
was reused; no source/UI build, layout review, public Caddy/TLS or deployment
verification is claimed. Catalog/parse caches were shared; a complete-result
cache miss is not a fully cold-run claim. Optional store lookups do not establish
live prices or stock.

### Benefits, compatibility and remaining work

Demonstrated substitutions and boilerplate-only reasoning now fail at the real
selection and persistence boundaries. More precise catalog coverage supplies
usable matching books instead of filling missing counts with wrong forms.
Concise incremental explanations and bounded optional enrichment reduce measured
first-card delay, while the diagnostic no longer confuses undelivered selections
or quota denials with successful empty recommendations. Stricter validation can
produce fewer books or reject old cached snapshots; no saved history is erased.

No API, SSE, schema, migration, dependency or provider replacement is involved.
Code-signature cache invalidation can cause cold work after deployment under the
shared allowance; existing cache keys and the budget row are not reset. Wider
catalog response bodies and bounded work lookups add some retrieval work, while
shorter/nonrepeated explanations can reduce model output/attempts. These are
bounded behavior changes, not guaranteed cost or latency savings for all inputs.

**Pending complete gate:** usage is **190/200**, leaving 10 attempts. A fresh
uncached canonical run needs at least 38 logical invocations before retries or
broadenings; the approved remaining allowance is insufficient. No higher cap,
additional database or reset is used. Further complete live acceptance must wait
for explicit additional authorization or the natural UTC reset. Until then the
round is not eligible to merge as a fully verified prompt/retrieval fix. Any
further substantive correction needs new source-matched verification.

The user-approved temporary cap is the only major policy exception in this
follow-up; no architecture, stack, schema, provider or scope decision was needed.
Upload/merge, first production deployment, host/domain, backup destination and
active backup scheduling remain separately authorized work. A passing automated
gate would still not establish complete semantic relevance or public-release
readiness.

### Closing receipt for the 200-cap window

- Final source-matched probe, present application/evaluation fingerprints and
  the verified Linux source archive match byte for byte. The archive checksum
  is recorded above; documentation/report additions after archiving do not
  change evaluated application/evaluation code.
- All 48 pending public files were reviewed. No configured model/catalog key or
  long private database-password match, unwanted attribution, or Chinese
  explanatory text was found. Intentional Spanish fixtures and original catalog
  content remain. Whitespace review passed. The verified Git owner identity is
  recorded in section 9; no commit or upload was performed.
- Read-only readiness under the restored **100** policy reported `cached_only`,
  healthy PostgreSQL/Redis, matching migration marker and **190 actual attempts**
  for UTC 2026-11-13. It issued zero model/catalog requests. Current-day uncached
  work stays blocked under the normal policy until natural UTC rollover;
  usage was not lowered to 100 or refunded.
- The exact temporary native frontend process tree and both temporary loopback
  data services/network were removed. Ports 3034 and 8034 were verified closed.
  Original application/data containers remained stopped and both original data
  volumes were verified preserved. Every disposable regression run removed its
  own labeled resources; unrelated projects were not stopped.
- Final status: implementation and local/database verification complete; a new
  complete passing live gate remains pending. The temporary 200-cap window is
  closed. No higher limit, scheduled continuation, upload, merge or deployment
  is implied.

## 11. Authorized merge-gate continuation

Date: 2026-11-13, Europe/Madrid. Following the completed 200-cap window, the user
requested merging this branch into main and starting the next implementation
round. Because the complete current-source gate was still pending, the user
explicitly approved **300 only for this acceptance continuation**, using the same
ledger, with merging conditional on successful acceptance. The previous 190
attempts were retained; this was not a new 300-attempt allowance in addition to
200. No architecture or provider change was introduced.

Readiness's explicit policy allowlist now includes 300 as well as 100/200, while
the default stays 100. The temporary-policy integration test covers both 200 and
300 with atomic boundary/concurrency and no-refund restoration; readiness also
verifies 300 without mutating rows or Redis keys. The runbook explains the
separate explicit approval. These operational verification changes do not modify
application/evaluation source fingerprints, prompts or retrieval after the
current-source supplementary probe.

A fresh verified original-database backup contained 3,368 books, 173 searches,
1,018 results, one migration marker and one budget row. Recovery fingerprints
matched, the original was unchanged and the recovered ledger remained blocked.
The new temporary loopback environment reused the same protected original data
volumes and kept all original workers stopped.

### Final complete real frontend gate

`backend/evals/results/eval-live-20261113-round25-merge-gate.json` completed all
20 canonical English/Spanish requests and returned exit 0 with
`complete: true` and `gate_passed: true`. All 144 streamed book cards matched
captured output. Authenticity, language, count, links and reason each passed all
20 cases. All 18 applicable first-book timings passed; the maximum was
**9,701.89 ms**. Both nonsense cases returned zero, with latency correctly
inapplicable. The 14 distinct previously recorded bad-snapshot ISBNs in the
regression fixtures were absent from recommendations.

The shared UTC 2026-11-13 usage advanced **190 to 234/300**, exactly **44 observed
logical calls and 44 reserved transport attempts**. No case exceeded six logical
calls or two broadenings. Nineteen complete-result flags were false; `en_comics`
was an explicit complete-result hit, backed independently by the earlier real
current-source seven-book probe. Parse/catalog caches remained shared and not
fully tracked. Neither this cache-aware gate nor manual checks establish
complete semantic relevance, provider-independent latency or public deployment.
No failed capture, suite case, threshold or earlier result was overwritten.

### Final local checks and cleanup

The final isolated Linux run passed lint, format, fresh migrations/model
agreement, **503 unit tests and 81 real PostgreSQL/Redis integration tests**:
**584 distinct tests**, zero failures/errors/skips. Source archive:
`backups/lumen-round25-regression-628886fe0a/source.tar`, SHA-256
`8ebc920a35056d9b63147252e09757615fcad68869dcbf2f7f0ff6b50138a02e`.
Application/evaluation source fingerprints match the final live report and the
archived tested source. Private logs, backup receipts and archives remain ignored.

The 300-cap backend was stopped. Read-only readiness under the restored 100
policy reported `cached_only`, healthy services, matching migrations and the
unchanged **234-attempt** current-day floor, issuing no model/catalog calls.
Uncached work remains blocked under normal policy until natural UTC rollover.
The exact temporary frontend process tree, data containers and network were
removed; ports 3034/8034 were closed. Original services stayed stopped and original
volumes were preserved. Disposable regression resources were also removed.

The source-matched complete gate now satisfies the prompt/retrieval merge
prerequisite; it does not approve production activation. Final public secret,
language, attribution, whitespace, owner-identity and staged-scope reviews are
required before the authorized push. Branch hosted checks must pass before the
non-rewriting main synchronization. Upload and merge authorization applies to
this round; the next round needs its own reviewed upload confirmation.

Final submission review covered all 49 public files, actual configured-secret
matches, language policy, owner identities and source/archive agreement. A literal
attribution scan initially flagged a third-party plot action in the original
catalog synopsis of *The Dragon Princess* (`9781434435453`), repeated in its two
ranking snapshots. Manual inspection confirmed it is story content, not project
authorship or tool credit; all three original evidence passages were preserved.
No actual project attribution violation or configured secret was found.

The pre-commit byte comparison also exposed the existing Windows-to-Git LF/CRLF
conversion (`core.autocrlf=true`). Reviewed working files and staged objects were
checked for identical content after only CRLF-to-LF normalization. The live
fingerprints continue to identify actual evaluated Windows bytes and the matching
Linux test archive; no capture hash or catalog evidence was rewritten. This
cross-platform evidence-checking limitation is part of the next round's audit
scope, not a source behavior change or waived check.
