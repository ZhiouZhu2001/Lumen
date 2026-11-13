# Lumen Update Version 26

## 1. Basic information

- **Round:** 26, an implementation round rather than an application release.
- **Date:** 2026-11-13, Europe/Madrid.
- **Branch:** `codex/update-26-acceptance-evidence`.
- **Baseline:** `cb21a112f6c75040cc5d455f6c0ac243098cd342`, verified on local and remote `main` before creating this branch.
- **Objective:** distinguish complete, source-compatible acceptance evidence from stale, partial or internally inconsistent reports without spending model allowance.
- **Actual scope:** a file-only diagnostic, 49 new offline tests, a retained audit artifact and operator documentation; eight public files. No recommendation behavior, prompt, catalog query, provider, frontend implementation, database or spending-policy change.

### Round 25 merge receipt

The user authorized uploading/merging the reviewed round, then explicitly
approved a temporary 300-attempt continuation on the same current-day floor of
190, conditional on full acceptance before merging. The completed real frontend
capture `eval-live-20261113-round25-merge-gate.json` passed all 20 canonical
English/Spanish cases: authenticity, language, count, links and reason each
20/20; 18 latency passes and two intended nonsense exceptions. Maximum first-book
delivery was 9,701.89 ms. Its 144 cards and cache evidence remain retained:
19 complete-result misses and one `en_comics` hit backed by the earlier real
current-source probe. It used 44 observed actual attempts, advancing the original
UTC 2026-11-13 singleton from 190 to 234/300. The default 100 policy was restored
without lowering usage. This was not an independent allowance or a cold-run claim.

All 49 reviewed files were committed as `cb21a11` with the full English
description and verified sole-owner author/committer identity. The branch was
uploaded, and all three [branch checks](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43519439782)
passed. Local main was fast-forwarded and remote main was synchronized to that
same commit; all three [main checks](https://github.com/ZhiouZhu2001/Lumen/actions/runs/43520657580)
also passed. An initial push awaited credential selection; only its owned
process tree was stopped, and an owner-qualified noninteractive retry succeeded.
No force push, pull request, release, deployment or history rewrite occurred.
This receipt closes the preparation-time statuses in the preserved round-25
record. Round 26 began on a clean tree after main synchronization.

## 2. Technologies used

No technology, dependency or paid service was added. Existing Python `argparse`,
`json`, `hashlib`, `datetime`, `math` and `pathlib` implement the diagnostic and
bounded validation decisions. Existing Pydantic-backed evaluation/replay helpers
recompute the established non-latency rules instead of creating a second set of
recommendation criteria. Pytest uses the actual committed full capture and
inconsistent copies. Existing Docker/locked Python tooling supplies a separate
Linux checkout simulation; its network is disconnected after dependency setup.
Ruff and native/Linux pytest verify formatting, behavior and portability.

## 3. Implementation

The new `scripts.check_acceptance_evidence` command reads an explicitly selected
capture. It requires version-2 HTTP evidence, runtime diagnostics, completion,
20 unique canonical cases and a passing six-check declaration. Case queries,
languages, categories and filters must match the active suite. Graph-only,
supplementary, failed or partial reports cannot qualify.

The command checks the complete existing evaluator source inventory and suite
checksum. Investigation found that Git's existing Windows text conversion made
51 source hashes and the canonical suite hash differ from committed LF bytes,
although their content was unchanged; four source hashes already matched exactly.
The diagnostic permits raw SHA-256 or uniform LF/CRLF variants only. It lists
the sources requiring conversion and still rejects other whitespace/code edits,
missing source keys and changed suites. No original capture hash is rewritten.
It records raw and LF-normalized input digests so checkout conversion does not
obscure the identity of the report data.

Saved pass labels are insufficient. The tool reuses the offline replay to check
authenticity, language, count, links and reasons against captured candidates.
Recommendations must agree with card ISBN/rank/reason fields, actual book frames
and the single terminal total. HTTP failures, unsupported filters, inconsistent
summaries or unexplained error frames fail verification. Intended nonsense
`no_results` frames remain compatible.

Stored first-book timings must be finite, nonnegative, at most 15,000 ms and
consistent with HTTP duration; nonsense timing must remain inapplicable. These
are checks on old measurements, never new timing observations. Shared same-UTC-day
budget snapshots must agree with the declared capture policy and summed actual
attempts. Six logical calls, two broadenings and explicit cache flags remain
bounded; complete-result hits cannot claim new model attempts. Missing or
cross-day accounting is not verified by this version.

The output distinguishes `verified` from `not_verified`, uses safe fixed issue
codes and always reports zero new model/catalog requests and no new latency
measurement. The captured model identity is represented by a digest; current
runtime configuration is explicitly unchecked. Optional output creation is
exclusive, so source captures and existing artifacts cannot be overwritten.
Invalid payloads and exception messages are not echoed.

## 4. File changes

| File | Change and before/after purpose |
| --- | --- |
| `backend/scripts/check_acceptance_evidence.py` | Added: file-only source/suite, case, replay, wire, retained-latency and usage consistency checks; previously operators relied on manual inspection and report labels. |
| `backend/tests/test_acceptance_evidence.py` | Added: 49 actual-capture, inconsistent-copy, portability, no-live-operation, safe-error and exclusive-output tests. |
| `backend/evals/results/acceptance-evidence-20261113-round26.json` | Added: successful disconnected-Linux audit of the committed full capture, recording 20 cases, 144 cards, 44 historical attempts, one cache hit and 51 LF/CRLF-equivalent sources; zero new service calls. |
| `docs/acceptance-evidence.md` | Added: usage, exit states, checksum behavior, evidence scope and limitations; distinguishes audit verification from a new live run or release authorization. |
| `docs/live-acceptance.md` | Modified: reference the file-only audit before relying on retained evidence while keeping fresh live acceptance requirements. |
| `docs/production-deployment.md` | Modified: add the optional evidence audit to the operator handoff without authorizing public ingress, model spending or release. |
| `README.md` | Modified: document the diagnostic and correct the old unconditional historical-persistence description to 17 valid saves and three explicit atomic rejections. |
| `update_version/Lumen_Update_Version_26.md` | Added: this round's implementation, verification, compatibility, submission proposal and the actual round-25 merge receipts. |

No file was deleted, no previous update record or capture was overwritten, and
private helpers/logs/archives remain ignored under `backups/`.

## 5. Project benefits

Operators can check whether an apparent passing report is complete, matches
current recommendation sources and agrees with its underlying output. A filename
containing `final`, a forged pass label, or a successful single-case probe is
insufficient. Uniform checkout conversion no longer creates a false source
mismatch, while actual edits still invalidate the evidence. The audit performs
no new model work, and output protection preserves both successful and failed
historical evidence.

## 6. Future impact and compatibility

The new command and version-1 audit artifact are additive developer/operator
interfaces. Public API/SSE fields, graph topology/retries, ISBN/FK validation,
privacy, database schema/migrations, providers, dependencies and default daily
policy are unchanged. The original application/evaluation fingerprint inventory
is unchanged, so this diagnostic/documentation round does not invalidate the
source-compatible round-25 recommendation gate.

Source identity covers application/evaluation Python and `app/stores.yaml` only;
frontend code, dependency locks, migrations and deployment/runtime settings are
outside that inventory. There is no age-based freshness or trusted-signature
guarantee. A consistently forged file can remain internally consistent. The
audit does not establish current provider credentials, quota, catalogs, public
ingress, production load or complete semantic relevance. Runtime readiness and
new live/public-path measurements remain separate. Future prompt/retrieval
changes still require a new complete live gate.

## 7. Verification

| Check actually performed | Result |
| --- | --- |
| Focused actual-capture and invalid-copy suite | **49 passed** in 20.94 s, including hidden reason/count failures despite unchanged pass declarations. |
| Full native Windows offline suite | **552 passed** in 31.05 s with blank keys and unreachable service URLs. |
| Final full Linux offline suite | **552 passed**, zero failures/errors/skips, with external networking disconnected after locked dependency preparation. These are the same 552 tests, not another 552 distinct tests. |
| Native and Linux Ruff lint/format | Passed without disabled checks. |
| Final lint invocation context | A repository-root invocation produced 57 import-classification errors under the wrong working-directory context. The documented command from `backend/` passed without source edits or disabled rules. |
| Actual canonical LF capture audit | `verified`: 20 cases, 144 cards, 44 retained actual attempts, one disclosed complete-result hit; 51 explicitly identified newline-equivalent source files. No new model/catalog calls or timing measurements. |
| Negative evidence coverage | Partial/supplementary/old failed reports, missing/duplicate cases, changed queries/filters/suite/source, missing source keys, false summaries/statuses, missing frames/wrong totals, over-limit/nonfinite/bool timings, changed usage/cap/day, unsupported filters, inconsistent cache flags, invalid private payloads and existing outputs all rejected. |
| Original capture/output preservation | Tests confirm unchanged input bytes and existing output contents, including attempts to use the input as output. |
| Linux checkout reproduction | Initial harness passed 552 tests but its 51-conversion assertion failed because archive creation inherited Windows conversion. That log remains retained. Explicit LF archive creation corrected the harness; the final audit observes all 51 conversions without loosening the assertion. |
| New database integration/migrations | Not rerun: this file-only command makes no database/runtime changes or connections. The unchanged baseline had 81 integration passes plus successful branch/main hosted checks; those are round-25 evidence. |
| New real recommendation/public UI/deployment checks | Not run: recommendation/frontend implementation is unchanged; the new diagnostic consumes retained evidence and does not measure live services. No production activation is claimed. |
| Cleanup | Both owned Linux containers removed; original backend/PostgreSQL/Redis containers remain stopped and temporary ports 3034/8034 remain closed. Original volumes were not mounted or modified by round-26 tests. |

Final LF source archive:
`backups/lumen-round26-lf-c9b50b4ac3/source.tar`, SHA-256
`28c43139826a83e405c4df25967193d7b5e79236376be3cff53306abaa96ce9d`.
The two new Python files match the tested archive after newline normalization.
The retained public audit is copied unchanged from that disconnected run.
Full private logs and JUnit evidence remain outside Git.

## 8. Approvals and remaining work

No major architecture, model/provider, core capability, schema, data migration or
spending decision was required for round 26. The user's request to start the
next round covers this routine verification work. Its model/catalog usage is
zero; the historical 300 policy in the audited capture does not grant new
allowance. The last live floor remains 234 for UTC 2026-11-13 under the restored
normal 100 policy.

The earlier main merge authorization applies to round 25 only. Review this
eight-file scope and obtain separate upload confirmation before publishing
round 26. A future merge also needs its corresponding authorization. Host,
domain, off-host backup/scheduling policy, first production release and
public-path verification remain separate pending work. Semantic relevance and
external freshness limits remain explicit rather than becoming an audit pass.

## 9. GitHub submission

**Proposed commit title:** `feat: audit retained acceptance evidence without live calls`

**Proposed commit description:**

Add a file-only acceptance-evidence command that verifies the complete canonical
HTTP suite, current recommendation-source inventory, recomputed non-latency
checks, actual delivery and retained timing/accounting consistency. Reject
partial, supplementary, stale-source and inconsistent records even when their
declared pass labels look successful. Allow only uniform Git LF/CRLF conversion
without rewriting captured hashes; retain raw and normalized input digests.

Keep errors safe, output creation exclusive and runtime configuration explicitly
unchecked. The audit makes no model/catalog/database calls and approves no new
live measurements, spending, upload or release. Add 49 regressions based on the
actual full capture, a successful disconnected-Linux audit, operator docs and
the historical persistence-documentation correction. No API, graph, database,
dependency, provider or daily-policy changes.

Verification: 552 offline tests pass on both Windows and disconnected Linux;
Ruff lint/format pass. The Linux audit verifies all 20 retained cases and 144
cards, discloses one cache hit and 51 newline-equivalent source files, and
reconciles the original 44 attempts without new usage. The initial archive
reproduction failure and tool limitations are documented. See
`update_version/Lumen_Update_Version_26.md` and `docs/acceptance-evidence.md`.

**Status at 2026-11-14 commit preparation (Europe/Madrid):** the user explicitly
authorized uploading this reviewed eight-file round and synchronizing main after
checks, then starting the next round. The existing files matched their reviewed
fingerprints before this submission-status update. The diagnostic/documentation
scope leaves recommendation behavior unchanged, so no new paid acceptance run
is needed. Source-compatible retained evidence still verifies without service
calls. Owner identities and public-content checks are reverified before commit.

At this snapshot the commit/push and hosted checks are still pending; subsequent
branch/main receipts will be recorded in the next round's update record. This
authorization does not cover uploading that next round, a pull request, release
or deployment. The successful remote-main receipts above concern round 25.

Final review confirmed the exact eight-file scope, no configured secret matches,
no Chinese explanatory text or unwanted attribution, unchanged recommendation
sources and the normal configured daily cap of 100. The retained audit matches
the disconnected Linux output byte for byte and its input digest matches the
committed canonical capture. The tested Python files match the archived sources.
Whitespace and the correctly scoped backend lint/format checks pass. Git author
and committer still match the verified project owner; no new commit was made.
