# Lumen Update Version 6

## 1. Basic Information

- Round: 6.
- Date: 2026-11-06, Europe/Madrid.
- Branch: `codex/update-6-evaluation-suite`.
- Baseline: `24fd6b52d9855e1efb9051567f4550da1e795205`, the uploaded Update 5
  recommendation-workflow branch. Update 6 depends on that unmerged work.
- Main baseline: `7d05697360369d0f88674fa148cd6f430d0f0aef`; unchanged locally
  and on GitHub when checked during this round.
- Objective: establish the specification's full bilingual evaluation set, execute
  every case against real services, and retain evidence before any main merge.
- Actual scope: evaluation tooling, offline regression coverage, command targets,
  documentation and one complete live graph evaluation. Product channels, filters
  and HTTP SSE integration were not implemented in this round.

The user explicitly chose to retain the feature branch and complete evaluation
instead of accepting a provisional merge based on unit tests and a smoke query.
The 20-case execution completed, but the full product evaluation gate did not
pass. This record does not claim that unfinished product checks were verified.

## 2. Technologies Used

- Python and `asyncio`: run the existing compiled recommendation graph, enforce
  a per-query timeout and continue collecting evidence after a failed case.
- Existing LangGraph, model wrapper and asynchronous HTTP clients: exercise the
  actual retrieval/ranking implementation and configured services. No replacement
  model provider, bibliographic source or application stack was introduced.
- Pydantic: validate the suite, supported language/category values, filter fields
  and result types; reject incomplete or duplicated coverage.
- PyYAML: load the query set with `safe_load`. It was already present as a
  transitive dependency and is now an explicit development dependency so the
  evaluation tool does not rely on an incidental dependency. The lockfile was
  updated without changing package versions.
- Standard-library Unicode normalization, regular expressions and URL parsing:
  implement the specification's simple proper-word heuristic and store-host,
  language and genre checks.
- JSON, SHA-256 and atomic file replacement: retain per-case checkpoints, suite
  identity, the baseline revision and an explicit completion/gate status.
- Existing pytest, Ruff, uv and Make: verify the evaluation logic and expose the
  documented `make test` and `make eval` commands.

No new application runtime technology or production service was introduced.

## 3. Implementation

### Bilingual query set

`backend/evals/queries.yaml` contains exactly 20 distinct cases, split evenly
between English and Spanish. Each language covers broad genres, a combined
publication-era/length constraint, comics, free-only reading, a niche request
and one nonsense query. Coverage validation rejects missing categories,
duplicate identifiers, duplicate queries and an incorrect language balance.

### Six checks

1. **Authenticity:** selected ISBNs must be unique, checksum-valid ISBN-13 values
   present in the current search's candidates.
2. **Language:** each selected candidate must match the requested book language.
3. **Count:** normal requests require 5–10 results; nonsense requires zero. The
   specification's fewer-than-five fallback is allowed for a niche request only
   after both broadening retries are exhausted.
4. **Links:** actual supplied card links must use recognized HTTPS store hosts.
   Spanish-only channels are rejected on English requests, Norma Comics requires
   comic/manga/graphic-novel metadata, and free-only requires a Gutenberg channel.
5. **Reason:** descriptions and reasons must be nonempty. Capitalized words
   outside sentence starts must occur in the title or description, after accent
   normalization; the English pronoun `I` is exempt.
6. **Latency:** an actual first-book HTTP SSE observation must be within 15
   seconds. Graph duration is stored separately and never substituted for it.

The reason check is deliberately identified as a heuristic, not proof of factual
grounding. It can flag comparisons with the user's request and ordinary
capitalized words, and can miss unsupported lower-case or sentence-initial
claims. A flag requires review; it is not automatically a confirmed invention.

### Honest handling of unfinished integration

The live adapter currently invokes the graph, while the existing HTTP endpoint
still returns keyword-search JSON. The graph has neither a final store-link
adapter nor an HTTP SSE timing observation. Those checks are `blocked`, never
silently passed. Requested filters are retained as unsupported because the graph
does not apply them. Eight cases request such fields.

Nonsense input has no expected first book, so only its latency is
`not_applicable`. A provider failure or timeout instead blocks every check for
that case. Unknown retry and candidate evidence stays null after an exception,
rather than being misrepresented as a successful empty response.

### Runner and report lifecycle

`python -m evals.run --validate-only` checks coverage without service calls.
`python -m evals.run --live` executes all cases sequentially with the existing
model/API configuration and a default 60-second timeout per query. The timeout
does not change the 15-second latency requirement.

Each live run writes a new timestamped report and updates it atomically after
every query. Reports include queries, candidate ISBNs, recommendations, retry
counts, durations, individual check explanations and aggregate counts, plus the
suite hash and Git baseline/dirty-tree status. Raw provider exception messages
and credentials are excluded. Existing report paths are rejected by the CLI.

An interrupted run retains `complete: false` and `gate_passed: false`. A complete
run exits successfully only if all 20 expected cases satisfy all six checks,
with no workflow errors or unsupported filters. A completed unsuccessful run
returns exit code 1 while preserving the evidence.

## 4. File Changes

| File | Change and purpose | Before and after |
| --- | --- | --- |
| `Makefile` | Modified; added phony `test` and `eval` targets. | The documented commands were absent; they now invoke offline pytest and the full live suite. |
| `backend/pyproject.toml` | Modified; declared PyYAML in the development group. | YAML support depended on transitive installation; it is now explicit for the evaluator. |
| `backend/uv.lock` | Modified; synchronized the development dependency declaration. | Added the two PyYAML group/metadata entries; existing package versions remain unchanged. |
| `backend/evals/__init__.py` | Added; defines the evaluation package. | No evaluation module existed; it can now be invoked with `python -m`. |
| `backend/evals/queries.yaml` | Added; stores all 20 bilingual cases and their constraints. | No fixed full-suite input existed; coverage is now versioned and validated. |
| `backend/evals/checks.py` | Added; validates coverage and evaluates the six requirements. | No automated gate existed; missing evidence, failures and acceptable nonsense latency are now distinguished. |
| `backend/evals/run.py` | Added; runs real queries and saves checkpoints/reports. | Only an individual manual graph runner existed; the full suite now produces retained machine-readable evidence and an exit status. |
| `backend/evals/README.md` | Added; documents commands, evidence, limitations and future adapters. | Evaluation operation and its current integration boundary were undocumented; both are now explicit. |
| `backend/evals/results/eval-20261106T192613667343Z.json` | Added; retains this round's actual live observations. | No complete bilingual run was recorded; all 20 outcomes and the unsuccessful gate are preserved. |
| `backend/tests/test_evals.py` | Added; 43 offline regression tests including parameterized cases. | No evaluator regression coverage existed; false passes, invalid suite coverage, bad links, timeout/error reporting and partial reports are now tested. |
| `update_version/Lumen_Update_Version_6.md` | Added; records this round. | Update 5 described the missing gate; this record documents the implementation, actual results and remaining blockers without rewriting history. |

No files were deleted. Existing application source, prompts, database migrations,
frontend code and unrelated working files were not changed in this round.

## 5. Project Benefits

The project now has a repeatable bilingual quality baseline instead of relying
on one successful query. Evidence distinguishes candidate authenticity from
recommendation quantity, reason heuristics, missing channel/filter features and
the unmeasured streaming requirement. An unavailable dependency or unfinished
adapter cannot produce a misleading green merge gate.

The live run exposed Spanish result-count failures and reason-check flags before
merging. It also confirmed that both nonsense cases returned no recommendations
after two retries. These results provide concrete priorities for later work.

## 6. Future Impact

- No API contract, database schema, data migration, deployment configuration,
  production dependency or frontend behavior changed.
- `make eval` now requires configured live services, incurs existing model/API
  usage and intentionally returns nonzero for failed or blocked checks.
- Future card/channel and SSE integrations must supply real output to the
  evaluator. Filters must be applied and verified before their unsupported
  status is removed. Changing only report labels would not satisfy the gate.
- Store URL template checks still require the specification's manual
  verification; host checks alone do not establish availability or stock.
- Reports identify a dirty working tree at execution because this evaluation
  round was not committed. They record the Update 5 baseline and suite hash;
  they do not claim to identify a released application revision.
- Later runs should be retained separately so changes can be compared with this
  unsuccessful baseline. Model outputs and public API catalogs can vary.

## 7. Verification

### Offline verification actually performed

- `python -m pytest -q -p no:cacheprovider`: **144 passed** in 1.78 seconds.
- Actual root `make test` using uv: **144 passed** in 1.92 seconds, including the
  101 pre-existing tests and 43 new evaluation tests.
- `ruff check app scripts tests evals`: **passed**.
- `ruff format --check evals tests/test_evals.py`: **passed**, five Python files.
- `python -m compileall -q evals`: **passed**.
- `python -m evals.run --validate-only`: **passed**; confirmed 20 cases, 10 per
  language and two nonsense cases, without live calls.
- `make -n eval`: **passed**; resolves to the same live runner executed below.
  The live run used the module command directly, rather than making a second
  set of paid API calls merely to repeat the Make target.
- `git diff --check`: **passed**.
- Retained-report integrity check: **passed**; all 20 case IDs match the suite,
  its SHA-256 matches the input file, aggregate counts match individual results,
  and recomputing the gate still returns false.
- Changed-content language/attribution scan: **passed**; no Chinese explanatory
  text or additional co-author/generated-assistant attribution was found.
- Broader `ruff check .`: **failed with six existing findings**, five in the
  unchanged initial Alembic migration and one import-order finding in the
  ignored local `scratch_google.py`. These were not hidden or changed as part
  of this evaluation round. The application/scripts/tests/evaluation scope
  listed above passes.

Tests cover incomplete coverage, duplicate cases, safe YAML loading, candidate
membership, duplicate/unknown ISBNs, language mismatch, result-count boundaries,
retry-exhaustion fallback, unsupported proper words, URL parsing and hosts,
channel language/genre/free-only rules, SSE timing bounds, false merge passes,
unsupported filters, timeout/provider/internal failures and atomic checkpoints.

### Actual live run

Command from `backend/`: `python -u -X utf8 -m evals.run --live` using the existing
configured model, `openai:gpt-5.4-mini`, and actual bibliographic API clients.

- Started: 2026-11-06 20:26:21 Europe/Madrid.
- Completed: 2026-11-06 20:28:17 Europe/Madrid.
- Cases completed: **20/20**; workflow exceptions: **0**.
- Total selected books across cases: **114**.
- Graph durations: **3.38–8.33 seconds**. These are not SSE latency measurements.
- Actual process exit: **1**, correctly indicating a gate that did not pass.
- Report: `backend/evals/results/eval-20261106T192613667343Z.json`.

| Check | Pass | Fail | Blocked | Not applicable |
| --- | ---: | ---: | ---: | ---: |
| Authenticity | 20 | 0 | 0 | 0 |
| Language | 20 | 0 | 0 | 0 |
| Count | 17 | 3 | 0 | 0 |
| Links | 0 | 0 | 20 | 0 |
| Reason heuristic | 15 | 5 | 0 | 0 |
| First-book SSE latency | 0 | 0 | 18 | 2 |

The authenticity/language passes include the two empty nonsense results; they
do not represent 20 nonempty recommendation lists. Both nonsense cases returned
zero picks after exactly two retries. Positive niche cases did not exhaust the
retry loop during this run.

| Case | Picks | Retries | Count | Reason heuristic |
| --- | ---: | ---: | --- | --- |
| `en_fantasy` | 7 | 0 | pass | pass |
| `en_thriller` | 8 | 0 | pass | pass |
| `en_short_modern` | 5 | 0 | pass | pass |
| `en_comics` | 7 | 0 | pass | pass |
| `en_free_classics` | 9 | 0 | pass | pass |
| `en_science` | 8 | 0 | pass | pass |
| `en_history` | 8 | 0 | pass | pass |
| `en_sea` | 5 | 0 | pass | pass |
| `en_niche` | 8 | 0 | pass | fail |
| `en_nonsense` | 0 | 2 | pass | pass |
| `es_fantasy` | 8 | 0 | pass | pass |
| `es_thriller` | 8 | 0 | pass | pass |
| `es_short_modern` | 5 | 0 | pass | fail |
| `es_manga` | 3 | 0 | fail | pass |
| `es_free_classics` | 3 | 0 | fail | fail |
| `es_science` | 9 | 0 | pass | pass |
| `es_history` | 5 | 0 | pass | fail |
| `es_sea` | 5 | 0 | pass | pass |
| `es_niche` | 3 | 0 | fail | fail |
| `es_nonsense` | 0 | 2 | pass | pass |

The reason flags include `Arctic`/`Ártico` in comparisons to the request,
`España`, `XIX`, `XX`, `Daniel Defoe`, `Estados Unidos` and `Guerra Civil` where
the heuristic did not find matching words in the allowed title/description.
These failures remain in the report; their presence is not asserted to prove
invented plot details. Count failures are not excused as niche fallbacks because
`es_niche` had zero retries.

No live channel/template verification or first-book HTTP SSE test was performed:
the required product implementations do not yet exist. Filter compliance was
not established. Full semantic grounding, relevance and UI-language quality are
not proven by the proper-word heuristic.

## 8. Approvals and Remaining Work

The user explicitly rejected a provisional merge exception and instructed that
the branch be retained while the full evaluation is completed. No major
architecture or product decision was introduced by this evaluation tooling.
There is no approved exception to the evaluation requirement.

The run completed, but the merge gate remains **NOT PASSED**. The next work is:

1. Diagnose the Spanish count failures and review the five reason-check flags
   without weakening real-book validation, grounding or the fixed retry limit.
2. Implement the specification's card/channel and filter support and connect
   the graph to the actual HTTP SSE path and frontend.
3. Verify store templates and measure real first-book delivery, then rerun all
   20 cases and resolve failures until the full gate genuinely passes.
4. Consider merging only after the gate is satisfied and corresponding user
   authorization applies. Persistence and other remaining MVP features remain
   future work; this round does not claim to complete them.

## 9. GitHub Submission

### Actual publication state

- Update 5 was committed as `24fd6b52d9855e1efb9051567f4550da1e795205` and pushed
  to `origin/codex/update-5-search-workflow` under the user's existing upload
  authorization. The remote head was verified during this round.
- Update 5 has not been merged. Remote `main` was verified at `7d05697`.
- Update 6 is local on `codex/update-6-evaluation-suite`, based on Update 5.
  Its changes are not committed or pushed; upload confirmation for this new
  scope is pending. No pull request, merge, release or deployment was created.
- The existing Git identity was checked as `ZhiouZhu2001` with the user's
  configured email. No additional author or collaborator attribution was added.

### Proposed commit title

`test: add bilingual evaluation suite and retain live baseline`

### Proposed description

Add the specification's 20-query English/Spanish evaluation suite and six
automated checks. Validate full coverage, distinguish missing evidence from
failures, retain atomic per-query reports and prevent incomplete or unsupported
results from passing the merge gate. Add Make targets, explicit development YAML
support, operating documentation and 43 offline regression tests.

Validation: all 144 offline tests pass; application, scripts, tests and evaluation
Ruff checks pass, as do scoped formatting and suite validation. A complete live
20-case run returned authenticity/language passes for all cases, three count
failures and five reason-heuristic failures. Links remain blocked in all cases,
and first-book SSE latency is blocked for the 18 non-nonsense cases. The merge
gate correctly remains unsuccessful. Broader lint still reports six pre-existing
findings outside the changed scope.

Compatibility: no application API, database, frontend, production dependency or
deployment changes. This branch depends on unmerged Update 5. Future channel,
filter and SSE integrations must provide real evidence and a passing full rerun
before merge. See `update_version/Lumen_Update_Version_6.md` and the retained
JSON report for details, limitations and the next steps.
