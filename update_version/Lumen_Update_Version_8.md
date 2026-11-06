# Lumen Update Version 8

## 1. Basic Information

- Date: 2026-11-06, Europe/Madrid.
- Branch: `codex/update-8-validated-ranking-retries`.
- Baseline: `587df5196982f47f4a17953a16f9ebb484453107`, the local Update 7
  checkpoint created before this implementation round.
- Dependencies at implementation start: local Updates 6 and 7, based on the
  uploaded but then-unmerged Update 5 branch. Main's publication baseline was
  `7d05697360369d0f88674fa148cd6f430d0f0aef`; verified publication is recorded below.
- Objective: implement the approved bounded ranking-feedback flow, preserve
  validated picks, reject unsupported output and verify the complete test scope.
- Actual scope: graph routing, shared grounding, ranking validation, intent
  handling, per-round evidence, caller compatibility, regression tests and docs.

The user explicitly approved the Update 7 proposal and requested passing tests.
The implementation keeps a fixed graph, one conditional branch, at most two
broadening attempts and at most six logical model invocations. Upload and main
merge were authorized after the implementation review, as recorded in section 8.

## 2. Technologies Used

No new library, primary stack, provider, bibliographic source or paid service was
introduced.

- Existing LangGraph: move the single stopping decision after ranking and
  validation while keeping the retry loop bounded.
- Existing Pydantic and LangChain structured output: parse meaningful reading
  intent, receive proposed picks and keep model/provider failures distinct.
- Python dataclasses: represent a ranking attempt's accepted picks, proposed
  picks, validation feedback, actual shortlist and whether a model was called.
- TypedDict/NotRequired: add internal state diagnostics without requiring every
  existing initial-state caller to provide them.
- Existing ISBN utilities: normalize spaces/hyphens, validate checksums and
  reject unknown or malformed identifiers before accepting a recommendation.
- Standard-library Unicode normalization and regular expressions: share the
  existing proper-word heuristic between production and evaluation unchanged.
- Existing pytest, Ruff, uv and Make: verify branch behavior, compatibility,
  grounding, intent handling, evidence and call budgets.
- Existing JSON/SHA-256 report tooling: retain both full live runs, actual
  ranking-round inputs/outputs and source fingerprints for independent replay.

## 3. Implementation

### Approved fixed flow

```text
parse -> search -> rank and validate -> one decision
                                      | >= 5 valid picks: finish
                                      | fewer, retries left: broaden -> search
                                      | two retries exhausted: valid subset/no_results
```

The previous branch counted candidates with descriptions before ranking. It
could stop even when the final valid recommendation list was too short. The
new `route_after_ranking` counts accepted recommendations instead.

Every retrieval round ranks at most once. A first-round success uses two logical
model invocations. The maximum remains bounded at one parse, two broadenings
and three rankings: six calls. An empty shortlist skips the ranking model call;
there is no hidden repair loop. Provider SDK transport retries are not counted
as separate logical graph invocations.

### Validation and retained picks

Each proposed recommendation must have a checksum-valid identifier matching a
retrieved candidate, the requested language, a source description and a nonempty
reason that passes the existing proper-word heuristic. Duplicate selections are
removed and final ranks are assigned consecutively. Arbitrary extra identifier
text or duplicated ISBN prefixes are rejected rather than converted into books.

The shared `app/grounding.py` implementation is AST-identical to the previous
evaluation functions. Moving it into the application does not relax the checks.
It remains a simple heuristic, not proof that every claim is factually grounded
or that a recommendation is relevant.

Accepted earlier picks survive later empty or partially rejected model answers.
The current attempt's accepted picks and retained picks are merged and
revalidated against the accumulated catalog. No unsupported book is added to
reach a target count. New candidate ISBNs are prioritized alongside retained
picks so that an old first-30 shortlist cannot permanently exclude later finds.
At most 30 candidates are still shown to each ranking call.

Specific validation issues and the remaining quantity shortfall feed the next
broadening and ranking attempts. The original reader query remains the ranking
request. Unsupported names in feedback are not permitted to become invented
search subjects.

Normal empty results remain distinct from model/provider failures. Persistently
nonempty but entirely invalid final output raises `LLMError` after the bounded
attempts. A valid empty answer produces `no_results` after the budget, while a
partial valid answer is preserved. The existing upstream failure path remains.

### Nonsense-input bug found during live verification

The first complete live run exposed one remaining failure: the Spanish nonsense
case became generic novel searches and returned six unrelated books. This run
was retained. Two new regression tests then reproduced the problem before the
fix: parsing invented a subject and the graph made unwanted catalog/ranking calls.

`ParsedQuery` now includes `is_book_request`. Initial parsing must identify
unintelligible input without inventing a genre, unknown author or generic
reading intent. Such input has no catalog searches or ranking model call and
terminates with zero picks at the existing conditional branch. Meaningful niche
topics, unfamiliar names and short reading requests remain valid.

This is a general structured intent decision, not a hardcoded evaluation-query
list. The field defaults to true for older internal snapshots, preserving replay
compatibility. Broadening preserves the initial understood reading intent instead
of inventing a different one. Initial nonsense rejection consumes only one
logical model call, with no broadening.

### Evidence and caller compatibility

Internal state now retains logical call counts and ranking rounds. Each round
captures its actual shortlist/input, raw proposed picks, accepted picks and
validation feedback. The evaluation runner uses the actual final priority
shortlist instead of reconstructing the first 30 accumulated books.

The standalone `scripts.try_rank` caller now reads `RankingAttempt.picks` and
prints feedback. A main guard prevents live service calls when importing that
script, allowing its real caller path to be tested offline.

The project convention and specification now record the approved flow. Previous
update records remain unchanged; this record establishes that Update 7's pending
proposal was explicitly approved and implemented here.

## 4. File Changes

| File | Change and before/after behavior |
| --- | --- |
| `CLAUDE.md` | Modified; replaces the pre-ranking candidate-count convention with the approved post-validation branch and six-call maximum. |
| `Lumen_Specifications.md` | Modified; documents approval, flow, retention, failure semantics, call budget and nonsense behavior. Other product requirements remain. |
| `backend/app/grounding.py` | Added; contains the unchanged heuristic previously present only in evaluation code, now usable by production. |
| `backend/app/graph/parse_query.py` | Modified; adds structured intent and prevents a rejected request from falling back to invented subject searches. |
| `backend/app/graph/broaden.py` | Modified; accepts validation feedback and preserves the original meaningful intent/format. |
| `backend/app/graph/rank.py` | Modified; adds `RankingAttempt`, explicit validation feedback, strict identifier/language/description checks and priority shortlists; previously returned cleaned picks without runtime grounding. |
| `backend/app/graph/state.py` | Modified; replaces candidate-count routing with validated-pick routing and adds optional internal diagnostics/intent state. |
| `backend/app/graph/workflow.py` | Modified; ranks before its single conditional branch, merges valid retained picks, tracks rounds/calls and handles uninterpretable input. |
| `backend/evals/checks.py` | Modified; imports the unchanged shared grounding helper; six-check criteria are preserved. |
| `backend/evals/run.py` | Modified; captures actual per-round evidence and call counts instead of assuming default shortlist order. |
| `backend/evals/README.md` | Modified; explains approved retry behavior, evidence, intent handling and remaining product blockers. |
| `backend/scripts/try_rank.py` | Modified; handles the ranking-attempt result and supports safe import for offline verification. |
| `backend/tests/test_route.py` | Modified; replaces obsolete pre-ranking candidate thresholds with eight post-ranking count/budget boundary cases. Description eligibility remains tested in ranking/workflow tests. |
| `backend/tests/test_workflow.py` | Modified; updates scripted node order and adds retry, new-book visibility, retention, grounding-feedback, six-call and intent regressions. Failure paths remain tested. |
| `backend/tests/test_rank.py` | Modified; uses checksum-valid fixture ISBNs and adds language, grounding, malformed-identifier, priority and manual-caller checks. |
| `backend/tests/test_parse_query.py` | Modified; adds rejected-intent cleanup coverage. |
| `backend/tests/test_evals.py` | Modified; verifies that recorded shortlist/input are the actual priority selection. |
| `backend/evals/results/eval-20261106T202506049745Z.json` | Added; retains the first full run and its nonsense-count failure before the intent fix. |
| `backend/evals/results/eval-20261106T203015501537Z.json` | Added; retains the corrected full run and its remaining blocked product checks. |
| `update_version/Lumen_Update_Version_8.md` | Added; records actual implementation, verification, approval and submission state. |

No files were deleted. Test fixtures now contain valid ISBN checksums because
runtime acceptance validates them; this does not bypass the ISBN checks. Twelve
new regression cases were added, while eleven obsolete route cases became eight
appropriate post-ranking cases: 161 tests versus the 152-test baseline.

## 5. Project Benefits

The graph can now recover from insufficient valid output instead of stopping on
metadata volume. Accepted recommendations survive subsequent attempts and new
books can enter the bounded shortlist. Unsupported-name and identifier failures
are handled before results reach a caller, with retained evidence for diagnosis.

Nonsense input cannot be intentionally converted into a generic reading request
by the understood-intent path. It avoids unnecessary catalog/model work when
correctly classified. Both intent and relevance still depend partly on model
behavior, so the full bilingual suite remains necessary after future changes.

## 6. Verification Actually Performed

### Offline checks

- Three new graph regressions failed before implementation: premature stopping,
  unsupported-name acceptance and absent bounded retries for unsuitable books.
  They passed after implementation.
- Two nonsense regressions failed after the first live run and passed after the
  intent fix. The original failed report was preserved.
- Final actual root `make test`: **161 passed in 2.21 seconds**.
- `ruff check app scripts tests evals` from `backend/`: **passed**.
- Scoped Ruff formatting: **passed**, 16 Python files.
- Suite coverage validation and `scripts.try_graph --help`: **passed** without
  additional live calls.
- `git diff --check`: **passed**.
- Python compilation of the touched application/evaluation/manual-runner scope:
  **passed**.
- Repository-language and attribution review: **passed**. A text scan matched
  the pre-existing prohibitions quoted in `CLAUDE.md`; reviewing the changed
  lines confirmed no new author/tool credit. No Chinese explanatory text was
  introduced; original bibliographic data remains intentionally unmodified.
- Final saved report replay: all 20 check verdicts reproduced in **0.024 seconds**
  after imports, without model/catalog requests. Actual replay CLI also matches.
- All **29** source fingerprints and the suite hash matched the final capture.
- Every captured shortlist was at most 30 books; retries were at most two;
  logical calls were at most six and matched `1 + retries + actual ranking calls`.
- AST comparison confirmed both grounding functions match the previous evaluator
  exactly. No reason/count criterion was weakened to produce passing results.

The existing broad-lint issues outside this scope, documented in Updates 6/7,
were not suppressed or repaired. Broad repository lint was not rerun; the backend
scope above was run. No frontend code changed, so frontend verification was not
repeated. No database write or migration was introduced or tested in this round.

### First actual full live run

Run: 2026-11-06 **21:25:06–21:27:38 Europe/Madrid**, using the existing configured
`openai:gpt-5.4-mini` model and actual bibliographic clients. All 20 cases ran.
Authenticity, language and reason checks passed for all cases. Count passed 19
cases and failed `es_nonsense`, which produced six picks after generic searches.
There were 56 logical model invocations, with a maximum of six per case.

Google Books also returned one HTTP 503 during this run; the existing partial
source-failure behavior preserved available results. No workflow invocation
failed. A complete graph duration reached 18.07 seconds; no SSE timing claim is
made from that duration. The run exited 1 and remains in the first report.

### Final actual full live run after the intent fix

Run: 2026-11-06 **21:30:16–21:32:14 Europe/Madrid**, with the same configured
model and real sources. All 20 cases completed, with zero workflow exceptions.
The 18 meaningful queries returned **126 selected books** in total; both nonsense
queries returned zero books, no catalog searches and no broadening.

| Check | Final outcome |
| --- | --- |
| Authenticity | 20/20 pass |
| Requested book language | 20/20 pass |
| Recommendation count | 20/20 pass |
| Reason heuristic | 20/20 pass |
| Buying/reading links | 20 blocked: adapter not implemented |
| First-book HTTP SSE latency | 18 blocked; two nonsense cases not applicable |

Both empty nonsense cases count as successful empty checks, not positive book
lists. Every meaningful query returned 5–10 picks; the run did not need the niche
fewer-than-five exception.

Four cases demonstrate the repaired retry behavior:

| Query case | Accepted picks by round | Logical calls | Whole-graph duration |
| --- | --- | ---: | ---: |
| `en_short_modern` | 3 -> 8 | 4 | 11.18 s |
| `es_short_modern` | 2 -> 6 | 4 | 8.95 s |
| `es_history` | 3 -> 7 | 4 | 8.28 s |
| `es_niche` | 2 -> 8 | 4 | 8.52 s |

There were **46 logical model invocations** across all 20 cases; successful
meaningful queries used two or four, and nonsense used one each. The six-call
worst case was verified offline and observed in the first live run. Meaningful
graph durations were 4.35–11.18 seconds, and nonsense took about 0.69–0.75 seconds.
These observations are not first-book HTTP SSE measurements or guarantees for
future public API/model responses.

The final live runner and replay both correctly exit **1** because the full
product merge gate remains blocked. Passing four core checks does not override
missing channels, unsupported filters or unmeasured streaming delivery.

## 7. Future Impact and Remaining Work

No new runtime dependency, public API contract, database schema, frontend behavior
or deployment configuration changed. The internal ranking helper now returns a
`RankingAttempt`; its graph and manual-script callers were updated and tested.
The parsed-query intent field is additive and defaults compatibly for older
snapshots.

Low-yield searches may consume the approved six logical model invocations rather
than stopping after the first ranking. Future daily spending safeguards must
count all actual logical calls. Additional raw/accepted round evidence increases
report size; the two retained reports total about 4.25 MB and exclude credentials.

Grounding remains heuristic and can reject translated/unsupported capitalized
names or miss lower-case factual errors. Model selection does not prove semantic
relevance. This successful core run is evidence, not a promise that all future
queries return enough suitable books.

Remaining product work includes card/channel rules, verified store templates,
request filters, the actual HTTP SSE/frontend integration, persistence and cost
safeguards. First-book delivery must be measured through the real HTTP path,
including retry cases, before the full gate can pass. The current HTTP endpoint
still returns keyword JSON and does not yet expose this graph to the webpage.

Rollback requires returning to the retained Update 7 baseline branch; no data
migration, production release or irreversible operation was performed.

## 8. Approval and GitHub Submission

The user explicitly approved the bounded ranking-feedback proposal on
2026-11-06. The existing stack, real-book constraints, maximum two broadenings
and six logical-call maximum were retained. No additional major decision was
implemented. At implementation review, no exception to the full evaluation gate
had been granted.

Publication follow-up: after being informed that links, filters and HTTP SSE
evidence still block the full gate, the user explicitly instructed uploading
this round and merging it into main. That newer instruction is treated as
authorization for this specific staged merge despite the disclosed blockers.
It supersedes the earlier instruction to keep the branch unmerged; it does not
turn the evaluation result into a pass or permanently change the merge policy.

Before this round, Update 7 was locally committed as
`587df5196982f47f4a17953a16f9ebb484453107`, with author and committer verified as
`ZhiouZhu2001` using the existing configured email. That checkpoint preserves the
previous round separately; its historical update record remains unchanged.

Publication was verified on 2026-11-06: implementation commit
`89c3eeec6ddf427727fb8c2f11349b897b8a3273` was pushed to
`origin/codex/update-8-validated-ranking-retries`. Main was then fast-forwarded
from `7d05697` to that same implementation commit and pushed. Remote head checks
confirmed both branches at `89c3eee`. The dependent Update 6/7 checkpoints and
Update 5 are therefore included in the published main history; the feature
branch is retained.

The upload check reran all 161 tests successfully in 1.95 seconds, along with
scoped lint/format checks. All pending commit author/committer identities were
verified as the user's configured identity, with no additional author credits.
This publication follow-up changes only the update record. No pull request,
release or deployment was created. The recorded full-product evaluation remains
unsuccessful because channels, filters and HTTP SSE evidence are still missing.

### Proposed commit title

`fix: retry after validating ranked book recommendations`

### Proposed description

Move the fixed graph's single retry decision after ranking and validation.
Preserve valid picks, prioritize new candidates within the 30-book shortlist,
share the unchanged grounding heuristic, and feed specific validation issues
into at most two broadening attempts. Track each ranking round and enforce the
approved topology's maximum of six logical model invocations.

Prevent unintelligible input from turning into invented generic book searches.
Adapt the manual ranking caller, retain actual shortlist evidence, and document
the explicitly approved flow in the specification and project conventions.

Validation: 161 offline tests and scoped lint/format checks pass. The corrected
full 20-case live run passes authenticity, language, count and reason checks in
every case. Both nonsense inputs return zero picks without catalog calls. The
first failed live run is retained, and offline replay reproduces the final
verdicts with matching source fingerprints. Channels and first-book HTTP SSE
evidence remain blocked, so the full merge gate correctly does not pass.

Compatibility: no public API, database, frontend, runtime dependency or deployment
change. Internal helper callers are updated; older parsed snapshots remain
readable. The published history includes the Update 6/7 and Update 5 dependencies.
See `update_version/Lumen_Update_Version_8.md` for approval, actual verification,
cost/latency limits and remaining product work. The user authorized uploading
and merging this branch as a staged exception after disclosure of the incomplete
full-product gate; the implementation upload and main merge have been verified.
