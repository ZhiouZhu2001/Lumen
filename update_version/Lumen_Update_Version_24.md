# Lumen Update Version 24

## 1. Basic information

- **Round:** 24; this is an implementation round, not an application release.
- **Date:** 2026-11-12, Europe/Madrid.
- **Branch:** `codex/update-24-live-acceptance`.
- **Known baseline:** `80325eec51779aebf84a2f070ae44d6357bc2e69`, synchronized local and remote `main` after the round-23 merge.
- **Objective:** measure the current 20-query bilingual six-check gate through the real frontend proxy, with explicit cache and shared-budget evidence.
- **Actual scope:** evaluation-only hourly admission isolation, detached diagnostic counters, bounded read-only budget snapshots, focused regression coverage, live acceptance evidence and operator documentation. Prompts, retrieval, providers, graph structure, store rules, API/SSE fields, database schema and acceptance thresholds are unchanged.

### Round-23 submission receipt

The reviewed 24-file operational-readiness implementation was committed as
`4b7866574ae50e12b1997b869fb685ec12447d3e`. The user explicitly confirmed uploading
that round and synchronizing remote `main`; the confirmation receipt is
`80325eec51779aebf84a2f070ae44d6357bc2e69`. The branch and `main` were pushed without
rewriting history. Hosted [branch checks](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43307585126)
and [main checks](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43308415970)
both completed successfully: Backend checks, Container checks and Frontend
checks. This receipt corrects the earlier record's then-current pending status
without rewriting its historical account. No public deployment occurred.

## 2. Technologies used

No dependency or service was added. The existing FastAPI/Uvicorn HTTP evaluator
uses the real application lifespan and a private in-process observer. A Python
context manager changes only the Redis hourly key namespace; the existing
PostgreSQL `DailyBudget` and guarded HTTP transport retain accounting authority.
Existing context-local observability supplies a copied counter projection.
`asyncio.timeout` bounds read-only ledger diagnostics. Pytest, Ruff, SQLAlchemy,
Alembic, PostgreSQL 17 and Redis 7 verify actual isolation/accounting behavior.
The existing native Next.js production build and proxy provide the measured
frontend path. Docker supplies isolated regression services and temporary
loopback-only access to the original stopped runtime's existing data volumes.
The existing backup tool verifies a private original-database archive by isolated
restore. HTTPX supplies bounded read-only store-destination diagnostics.

## 3. Implementation

### Runtime evidence and admission isolation

`current_search_metrics()` returns a detached dictionary containing only complete
result-cache reuse, logical model calls and actual reserved transport attempts.
It returns null outside a bound search and never exposes the mutable trace,
reader identity, search UUID, query or credentials.

The HTTP evaluator's optional `--isolate-hourly` creates a unique expiring Redis
IP-counter namespace with the unchanged 20-search limit. It preserves the exact
daily-budget object used by both admission and the outbound model transport.
The integration test exhausts the original hourly namespace, proves admission in
the evaluation namespace without changing original keys, then proves that two
other namespaces cannot spend beyond the same one-attempt synthetic allowance.
That synthetic database belongs only to offline integration verification; real
calls use the original live ledger and its unchanged 100-attempt policy.

Reports remain version 2 for existing replay compatibility and add
`runtime_evidence_version: 1`. They retain the original six checks and add HTTP
status, nullable per-case runtime counters/cache evidence, the actual hourly
namespace and cache policy. Budget reads occur before the run and after each
completed case; the latest value is retained as `budget_after`. Only known,
nondecreasing counts on one UTC day produce a numeric delta. Unknown reads,
rollover and inconsistent decreases are explicit. These reads neither reserve
nor initialize allowance. Shared deltas can include other active workers.

Shared result, parsing and catalog caches are retained. Complete-result reuse is
measured; individual parse/catalog cache reuse is not fully instrumented. A
result-cache miss therefore does not establish an entirely cold run. Missing
observer evidence stays null instead of becoming zero usage or a claimed miss.

### Actual runtime preparation

The original PostgreSQL, Redis and older backend containers were stopped. Rather
than starting their old wildcard host bindings, temporary labeled data services
mounted the exact original PostgreSQL and Redis volumes through dynamic loopback
ports. The original backend stayed stopped. No daily-ledger clone, new live
allowance, reset, refund or private environment-file change was performed.

Read-only readiness reported the current migration marker `6a81e4b39c20`, usable
Redis and a known 0/100 logical allowance for UTC 2026-11-12 before live work.
A verified private pre-run backup retained 225 books, 74 searches, 404 search
results, one migration marker and one daily-ledger row. Restored content hashes
matched; only the disposable recovered copy was blocked. The source was not
modified by backup verification. Archives and temporary credential-bearing
configuration remain Git-ignored under private `backups/` permissions.

The frontend was freshly built with backend keys absent from its environment,
then started on `127.0.0.1:3034` forwarding to the evaluator on
`127.0.0.1:8034`. The native proxy path is the live target; there is no silent
direct-backend fallback or public deployment claim.

## 4. File changes

| File | Change and purpose |
| --- | --- |
| `backend/app/observability.py` | Modified: expose a detached internal counter projection; previously the evaluator had no safe accessor. |
| `backend/evals/http_run.py` | Modified: retain HTTP/cache/runtime/budget evidence and isolate only hourly admission on request; previously reports omitted this evidence. |
| `backend/evals/run.py` | Modified: expose the optional HTTP-only isolation flag without changing default admission or the six-check suite. |
| `backend/tests/test_eval_runtime_evidence.py` | Added: nine cases verify detached metrics, known/unknown snapshots, zero usage, UTC rollover and refusal to report a decreasing count as a refund. |
| `backend/integration_tests/test_eval_runtime_evidence.py` | Added: real PostgreSQL/Redis test of original-key preservation and a shared daily limit across hourly namespaces. |
| `backend/evals/README.md` | Modified: document runtime evidence and replace obsolete Redis-daily-counter/reconciliation guidance with the approved PostgreSQL policy. |
| `docs/live-acceptance.md` | Added: preparation, actual proxy path, cache/accounting interpretation, store-destination limits and release boundaries. |
| `backend/evals/results/eval-live-20261112-round24-initial.json` | Added: actual 20-case frontend HTTP capture with original source/candidate/check evidence and additive runtime accounting diagnostics. |
| `backend/evals/results/eval-live-20261112-round24-review.md` | Added: six concrete type-mismatch examples, initial latency observations and the proposed correction scope; automated heuristic passes previously concealed these semantic gaps. |
| `backend/evals/results/store-links-20261112-round24.json` | Added: seven real emitted-link header probes, redirects and explicit absence of inventory/product-page verification. |
| `update_version/Lumen_Update_Version_24.md` | Added: implementation, submission receipt, verification and remaining work for this round. |

The round contains 11 public changed/added files. No existing historical report
is overwritten. No source file was deleted. Private archives, helper scripts,
temporary configuration, raw local logs, JUnit files and verification manifests
remain ignored under `backups/` and are outside the submission scope.

## 5. Project benefits

Acceptance evidence now distinguishes cached work from new model attempts and
separates evaluation admission from the spending policy. Operators can explain
denied or incomplete runs without deleting interactive counters or granting a
second allowance. The real proxy measurement exposes current response-time
failures that offline transport probes cannot establish. Explicit uncertainty
prevents a reachable store host or known ISBN from becoming a false inventory
or semantic-quality claim.

## 6. Future impact and compatibility

There is no public API/SSE contract, database migration, dependency, provider,
scope, production host or recurring-service change. Existing version-2 captures
and replay remain compatible with the additive diagnostic fields. No change to
the 15-second first-book requirement or the two-broadening/six-logical-call limit
was made. The existing backend-code signature changes the effective parse/result
cache namespace on deployment; this can cause cold work under the same cap.
Existing cache keys and stored allowance are preserved.

These local measurements do not establish public Caddy/DNS/TLS behavior, browser
layout, production load, complete semantic relevance, inventory, prices or
future provider availability. Public release and scheduler activation remain
separate approved deployment work. Private original-volume access was temporary
and must not become a new exposed production configuration.

## 7. Verification

| Check actually performed | Result |
| --- | --- |
| Native complete offline backend suite | 410 passed; no live model/catalog requests. |
| Independent isolated Linux lint and format | Passed; all 116 checked Python files were already formatted. |
| Isolated Linux complete offline suite | 410 passed in 6.01 seconds. |
| Real isolated PostgreSQL/Redis integration suite | 76 passed in 20.63 seconds. Together with the offline suite, 486 distinct backend tests passed; native repetition is not counted twice. |
| Fresh migrations and model agreement | Passed on the disposable regression database. |
| Canonical suite validation | 20 cases, ten per language, including two nonsense cases; no service calls in this validation. |
| Native Next.js production build | Passed with loopback backend configuration and backend keys absent. |
| Original runtime readiness | Ready, migration marker matched, known logical 0/100 UTC-day allowance before the live run; remote credentials initially unverified. |
| Original application backup/isolated recovery | Verified matching public-table contents; source unmodified, recovered allowance blocked. |
| Hosted round-23 branch and main checks | Three jobs passed on each event, linked above. |
| Full real frontend HTTP acceptance | All 20 cases completed; **gate not passed**, exit 1. Authenticity, language, count, link rules and reason heuristics each passed 20/20. Latency passed 15, failed 3, and was not applicable to the two zero-book nonsense cases. |
| Real runtime accounting | Original shared UTC-day allowance increased from 0 to **54/100**, leaving 46 at completion. Observed logical calls and reserved attempts both totaled 54, with at most six logical calls and two broadenings per case. All 20 HTTP responses were 200; no provider/admission failure was hidden as an empty success. |
| Cache evidence | All 20 captured complete-result cache flags were false; shared parsing/catalog caches were retained and are not fully tracked. This is not a claim of fully cold catalogs/parsing. |
| Version-2 offline replay compatibility | The new capture loaded successfully and reproduced 20/20 passes for each non-latency check without keys or usable service endpoints. As designed, replay blocked 18 live timings, kept two nonsense timings inapplicable and exited 1; stored timing was not presented as a new HTTP pass. |
| Actual store-destination headers | Seven samples, one per emitted store/language pair, returned HTTP 200 after bounded redirects or HEAD-405 GET-header fallback. No stock, product relevance or challenge-page content was verified. Abacus redirected one sample with `noresults=true`, demonstrating why reachability does not prove a matching result. |
| Public content/source review | No configured API-key or long private database-password matches, unwanted attribution or Chinese explanatory text in the 11-file pending scope. Spanish queries and original bibliographic text remain intentional. All evaluated application/evaluation source fingerprints still matched the final source. |
| Final read-only readiness and cleanup | Original allowance remained 54/100 with usable services before shutdown. Owned live containers/network and the native frontend process tree were stopped/removed; original containers remained stopped and both original data volumes were verified preserved. |

The isolated regression services and their owned resources were removed. No public
DNS/TLS issuance, production activation, active backup timer or browser layout
review was performed; none was part of this backend/evaluation change.

### Failed first-book checks

| Case | Actual first-book receipt | Requirement |
| --- | --- | --- |
| `en_fantasy` | 16,610.93 ms | At most 15,000 ms. |
| `en_short_modern` | 17,152.19 ms | At most 15,000 ms; niche count treatment does not waive latency. |
| `es_short_modern` | 15,614.80 ms | At most 15,000 ms; both retries and all filters remain required. |

The actual capture contains 118 cards. The five non-latency automated checks
passing does not negate the semantic failures in the accompanying review. No
prompt/retrieval correction or second real model run was performed, and no
latency value was replaced with a cached rerun. Reports remain separate from
the private pre-run database backup and can be reviewed without exposing earlier
stored reader queries.

## 8. Approvals and remaining work

There was no major architecture, provider, schema, spending-limit or scope
decision. The user separately confirmed round-23 upload/main synchronization.
An initial automatic approval review rejected real round-24 calls because that
confirmation did not explicitly cover their possible cost; the rejected command
did not execute. The user then explicitly approved the 20-query real model and
catalog acceptance under the existing shared 100-attempt cap. That authorization
covers the bounded run, not a new paid service, repeated unrestricted testing,
round-24 upload or public release.

The first authorized local launch failed in the external temporary helper's
argument-separator assertion before starting the evaluator or making a provider
call. The helper was corrected and the real run was started. No check or product
policy was bypassed. Live failures, limitations and next work are retained below.

Manual review identified authentic but inappropriate activity books, expedition
reports, history and literary criticism in novel requests. The retained review
lists six examples by case and ISBN, including an explicit history-versus-fiction
concession missed by the existing lexical rule. These are release-blocking
quality defects even where all five non-latency automated checks pass. The next
implementation round should preserve requested reading form, reject clear type
substitutions and concessions using these real snapshots, and investigate the
optional lookup before first-card delivery. This round does not claim those
fixes are implemented. Changed prompt/retrieval behavior still requires a new
complete live gate under the original allowance and appropriate call approval.

## 9. GitHub submission

**Proposed commit title:** `test: capture shared-budget frontend live acceptance`

**Proposed commit description:**

Improve the 20-query bilingual HTTP acceptance runner with explicit complete-result
cache evidence, observed model calls/attempts, HTTP status and bounded read-only
shared-budget snapshots. Add optional evaluation-only hourly admission isolation
while preserving the original PostgreSQL allowance, unchanged 100-attempt cap,
production reservation transport and existing cache keys. Retain version-2 replay
compatibility and all six checks, thresholds, prompts and retrieval behavior.

Add focused offline and real PostgreSQL/Redis regression coverage, update obsolete
daily-accounting guidance, and document live preparation and evidence limits.
Retain the actual frontend-path report and bounded emitted-store diagnostics,
including unsuccessful checks, without treating local reachability as public
deployment or book availability. No API/schema/dependency/provider change is
introduced; backend code signatures can cause cold parse/result work under the
existing allowance.

The current live gate does not pass the 15-second first-book requirement for
every ordinary query. Manual review also demonstrates type-mismatched books
that pass the current metadata/reason heuristics. Retain these failures and the
concrete correction scope rather than claiming release readiness.

Validation includes 410 offline and 76 integration tests, lint/format, fresh
migration/model agreement, native frontend production build, original-database
readiness and verified private backup recovery. The 20-case real capture completed
with 54 shared-budget model attempts, five automated checks passing for every
case, three first-book latency failures and two inapplicable nonsense timings.
Manual review retains six type-mismatch examples. Seven emitted store-link
samples were HTTP-reachable without establishing inventory or page content.
See `update_version/Lumen_Update_Version_24.md`, the retained review/report and
`docs/live-acceptance.md` for evidence, compatibility and remaining corrections.

**Actual submission status:** the 11-file round-24 scope is reviewed and remains
uncommitted on `codex/update-24-live-acceptance`, not uploaded or merged.
Author/committer configuration was verified as the project owner's configured
identity. Public content, evaluated source fingerprints and whitespace checks
passed. Round-24 upload has not been confirmed; round-23 authorization does not
extend to these changes. Recheck the pending scope and identity when preparing
the eventual commit/upload. No attribution or co-author trailers were added.

### Submission confirmation, 2026-11-12, Europe/Madrid

The user explicitly confirmed uploading the reviewed 11-file round-24 branch and
synchronizing remote `main` after successful hosted code checks. All reviewed
file fingerprints matched before this receipt was appended, and the configured
author/committer identities matched the verified project owner. The three live
latency failures and semantic mismatches remain unchanged and visible. This
round changes evaluation evidence and internal diagnostics, not prompts or
retrieval, so merging it does not waive the full live gate required for later
prompt/retrieval corrections. No production release or public deployment is
authorized. The final commit/main checkpoint and hosted results will be recorded
in the next round's receipt after completion.
