# Lumen Update Version 7

## 1. Basic Information

- Date: 2026-11-06, Europe/Madrid.
- Branch: `codex/update-7-recommendation-grounding`.
- Baseline: `c65e6140343d9587dbcf042de00a524649ee14d4`, a local checkpoint
  of the completed Update 6 files, created before this round's implementation.
- Dependencies: unmerged Update 5 and local, unpublished Update 6. Main remains
  at `7d05697360369d0f88674fa148cd6f430d0f0aef`.
- Objective: investigate the observed count/reason failures, improve retrieval
  and grounding instructions, and make future failures reproducible offline.
- Actual scope: two prompt refinements, version 2 evaluation evidence, an offline
  replay command, eight regression cases, a new full live report and this record.

The prompt changes did not resolve the quality gate. This round provides better
evidence and a concrete follow-up proposal; it does not claim to have fixed all
quantity or grounding failures. No search-graph topology change was implemented.

## 2. Technologies Used

No new library, model provider, data source or production service was added.

- Existing LangChain structured-output prompts: refine catalog search terms and
  constrain facts used in recommendation reasons.
- Existing Pydantic schemas: reconstruct captured books, parsed queries and picks
  without contacting external services.
- Standard-library JSON and SHA-256: retain normalized candidate evidence and
  identify the application/evaluation source used by an uncommitted working tree.
- Existing pytest, Ruff, uv and Make: verify evidence capture, offline replay,
  rejection of insufficient reports and compatibility with the existing tests.
- Existing LangGraph and asynchronous catalog clients: execute the unchanged
  bounded workflow in the live comparison run.

## 3. Investigation and Implementation

### Evidence and findings

The existing count and unsupported-name tests were run first. A catalog-only
probe repeated the three failed Spanish searches from Update 6 without model
calls. The manga case returned 16 described candidates, including magazines,
travel guides and unrelated novels. Merely having five descriptions does not
establish that five candidates match the reader's request.

The old report retained ISBNs and selected reasons, but not the descriptions
used to check those reasons. Later catalog responses cannot reliably reconstruct
the original input. Two new evidence regressions were written and run before
the fix: both failed with missing `parsed_query`/snapshot fields. After the fix,
the same tests pass and reconstruct identical check results without a network.

Three explanations were considered: metadata volume being mistaken for enough
matching books; names leaking from authors/the request into reasons; and the
shortlist/description limits hiding useful context. The new live snapshots show
that all five count failures had only 6–15 described candidates, all within the
30-book shortlist. The shortlist cap therefore does not explain those failures.
Description truncation and relevance remain separate limits, not proven fixes.

For the astronomy case, the live log also showed an unknown 16-digit ISBN that
the existing membership guard dropped. It would be incorrect to attribute every
short list solely to insufficient catalog coverage. The core guard remained in
place and did not turn malformed model identifiers into invented books.

### Prompt changes

- Catalog parsing now treats free availability and reading format as channel
  constraints, rather than adding them as story subjects. It retains requested
  format genres such as manga in catalog searches. Search terms never establish
  that a free edition exists.
- Ranking now explicitly restricts proper names to the same candidate's title
  or description, excludes author-field-only names as evidence, and prohibits
  importing requested locations merely to say that a book is not set there.
  It also prohibits inferring public-domain/free availability from a familiar
  author or title.

These are instructions to the model, not guarantees enforced by its output
schema. The live results below demonstrate remaining violations. The heuristic,
ISBN guard, count criteria, five-candidate threshold, maximum two broadenings,
30-book cap and 600-character ranking-description cap were not weakened.

### Reproducible version 2 reports

Each successful case now saves:

- The latest parsed query and the number of all candidates with usable descriptions.
- Ordered shortlisted ISBNs and the formatted candidate text supplied to ranking,
  including the existing truncation and shortlist limits.
- Normalized candidate snapshots with ISBN, title, authors, language, full source
  description, genres, source name, publication year and page count.

Snapshots exclude cover URLs, ratings and raw provider payloads. They preserve
the full description because that is the existing heuristic's reference data;
the separate ranking input shows precisely which truncated description the
model saw. Failed workflows save null evidence rather than fabricated empty
catalogs.

The report also saves `report_version: 2` and SHA-256 fingerprints of all 28
application/evaluation Python files. This identifies the evaluated source while
retaining the honest dirty-tree flag. Existing version 1 reports are preserved.
The new fields are additive; no historical data was rewritten or migrated.

### Offline replay

From `backend/`, run:

```console
uv run python -m evals.replay evals/results/eval-20261106T194316599558Z.json
```

The command reconstructs candidates and picks and runs the current checks. It
requires a complete version 2 report with 20 unique expected cases, a matching
suite hash and matching query/language/category metadata. It rejects incomplete,
legacy or missing-evidence captures. It does not modify the report, call the
model/catalog, generate new picks, validate a changed prompt or measure latency.

The current graph capture cannot supply links or first-book SSE observations,
so replay keeps those checks blocked and exits with 1. A passing replay must
never be substituted for the specification's future live product evaluation.

## 4. File Changes

| File | Before | After |
| --- | --- | --- |
| `backend/app/graph/parse_query.py` | Availability could enter subject searches. | Prompt separates channel constraints from catalog subjects and retains format genres. |
| `backend/app/graph/rank.py` | General description-only instruction. | Explicit restrictions on author-only/request-only names and unverified free availability. |
| `backend/evals/run.py` | Reports retained candidate ISBNs without source descriptions. | Saves normalized evidence, ranking input, shortlist/count diagnostics, report version and code fingerprints. |
| `backend/evals/replay.py` | Absent. | New offline evidence reconstruction and checking command with strict completeness checks. |
| `backend/evals/README.md` | Covered version 1 live execution only. | Documents version 2 evidence, offline replay, its exit status and limitations. |
| `backend/tests/test_evals.py` | 43 evaluator tests. | Eight additional cases for reproducible snapshots, failed-workflow evidence and valid/invalid replay input. |
| `backend/evals/results/eval-20261106T194316599558Z.json` | Absent. | New complete, unsuccessful real-service run with captured evidence. |
| `update_version/Lumen_Update_Version_7.md` | Absent. | This round's findings, actual changes, verification and pending proposal. |

No files were deleted. No application API, database migration, frontend code or
deployment configuration changed. Existing unrelated working files were preserved.

## 5. Project Benefits

Failures can now be reproduced in milliseconds from the data actually checked,
rather than inferred from a later catalog response. The source fingerprints
distinguish an uncommitted evaluation from an unspecified application revision.
Separate rankable/shortlist/pick counts expose premature stopping and guard
rejections without disguising them as successful zero-result responses.

The prompt refinements clarify existing product constraints. Their practical
quality benefit is not yet established: this single new run still fails and is
not a controlled statistical comparison.

## 6. Verification Actually Performed

- Initial targeted count/reason regressions: two passed, confirming the existing
  checks detect those failure patterns.
- New evidence tests before implementation: two failed on missing capture fields.
- Full pytest after evidence capture: 146 passed.
- Full pytest after replay implementation: 152 passed in 1.83 seconds.
- Final actual root `make test`: **152 passed in 1.88 seconds**.
- `ruff check app scripts tests evals`: passed after correcting a new exception
  type lint finding. Scoped formatting and `git diff --check` passed.
- A final invocation of that file scope from the repository root instead of
  `backend/` reported 13 import-order findings. Ruff's displayed settings confirm
  that its inferred source root changes with the working directory, changing
  first-party import classification. The documented backend-directory invocation
  was repeated and passes. No import rewrites or configuration suppressions were
  applied to conceal the root-invocation result.
- Live runner: all 20 cases completed using the existing configured
  `openai:gpt-5.4-mini` model and actual bibliographic clients; exit 1, correctly
  reporting an unsuccessful gate.
- Actual replay CLI: reproduced the summary below offline, retaining blocked
  product checks and exit 1.
- Replay consistency probe: all 20 complete case verdicts reproduced identically
  twice in 0.043 seconds after imports; all 28 source fingerprints and the suite
  hash matched the captured data. No network calls were involved in replay.
- Legacy Update 6 report: replay correctly rejected its missing candidate snapshots.
- The prior broad-lint findings outside the changed scope were not repaired or
  suppressed. Broad lint was not rerun; the scoped check above was run.

### Actual live observations

Report: `backend/evals/results/eval-20261106T194316599558Z.json`.
Started 2026-11-06 20:43:17 and completed 20:45:20, Europe/Madrid.
All 20 graph invocations completed without a workflow exception, selecting 109
books in total. Individual graph durations were 3.52–9.81 seconds; these are
not first-book SSE timings.

| Check | Update 6 | Update 7 |
| --- | --- | --- |
| Authenticity | 20 pass | 20 pass |
| Language | 20 pass | 20 pass |
| Count | 17 pass, 3 fail | 15 pass, 5 fail |
| Reason heuristic | 15 pass, 5 fail | 16 pass, 4 fail |
| Links | 20 blocked | 20 blocked |
| First-book SSE latency | 18 blocked, 2 not applicable | 18 blocked, 2 not applicable |

The count result worsened in this observation, while reason flags decreased by
one. Different catalog searches, catalog responses and model output mean this
does not isolate the causal effect of either prompt change. Neither run passes
the gate and neither establishes complete semantic quality or filter compliance.

| Failed count case | Described candidates | Shortlisted | Picks | Retries |
| --- | ---: | ---: | ---: | ---: |
| `en_short_modern` | 14 | 14 | 3 | 0 |
| `en_science` | 15 | 15 | 4 | 0 |
| `es_short_modern` | 6 | 6 | 2 | 0 |
| `es_history` | 12 | 12 | 2 | 0 |
| `es_niche` | 7 | 7 | 2 | 0 |

The four reason-check failure cases are `en_free_classics`, `en_history`,
`es_manga` and `es_free_classics`. Snapshot inspection confirms author-field
overlap for the flagged `Arthur Conan Doyle` and `Defoe` names. Other flags may
involve translation or cross-candidate/request context and require review;
the heuristic alone is not proof of fabricated facts.

Both nonsense cases returned zero recommendations. English exhausted one
broadening before ranking unrelated candidates and choosing none; Spanish
exhausted both retries with no rankable candidates. This differs from Update 6
and is preserved as observed, not normalized to an expected retry count.

No live store-template check, filter verification or HTTP SSE timing test was
performed: these product integrations are still missing. No successful full
product evaluation or main merge is claimed.

## 7. Future Impact

No runtime dependencies, API contracts, database schemas or deployment behavior
changed. Additional report evidence uses more local disk space and retains public
bibliographic descriptions; it excludes credentials and raw request data. The
new report is 1,330,654 bytes and preserves the original unsuccessful baseline.

Future prompt work needs another real-service evaluation. Offline replay can
test check logic against existing snapshots, but cannot establish how a new
prompt behaves. Future channel/SSE adapters must extend capture and replay to
consume real product evidence rather than removing blocked labels.

## 8. Pending Major-Decision Proposal

**Status: investigation/proposal only; not approved and not implemented.**

The current fixed flow stops retrieving as soon as five candidates have
descriptions, then ranks once and ends. It has no way to react when ranking
produces fewer than five valid matching books or when validation drops malformed
ISBNs/reasons. The live counts above demonstrate this mismatch.

Recommended follow-up: keep a fixed, bounded graph and move its single
enough-results decision after ranking and validation:

```text
parse -> search -> rank and validate -> enough valid results?
                                      | yes: finish
                                      | no, retries left: broaden -> search
                                      | no, two retries used: finish with valid subset/no_results
```

- Rank at most once per retrieval round; do not add a separate unbounded repair
  loop. Pass specific validation/relevance shortfalls into the next broadening
  and ranking attempt.
- Retain ISBN membership validation, fact-grounding checks, the 30-candidate
  limit and a maximum of two broadenings. Never pad with fabricated or unrelated
  books. Preserve valid picks/evidence when incorporating new candidates.
- Typical first-round success still uses two model calls. The worst-case model
  call count becomes one parse, two broadenings and three rankings: **six calls**,
  versus the current maximum of four. A case that currently ends after its first
  ranking could use six instead of two. More latency and model usage must be
  measured; this proposal does not guarantee the 15-second SSE requirement.
- Share the grounding check at an application/evaluation boundary rather than
  importing development evaluation modules into production code. False-positive
  behavior must be tested and disclosed.

Alternatives: retain the current flow and continue improving retrieval/prompt
quality, which leaves this stopping-condition mismatch; or add a separate repair
call to ranking, which can fix identifiers/reasons but cannot find missing books
and adds another call budget. Raising the metadata-count threshold alone cannot
establish relevance or prevent the demonstrated invalid-identifier shortfall.

The recommended change affects the fixed search flow and worst-case model
usage, so approval is required by the root `AGENTS.md` major-change rule before
implementation. It is distinct from upload confirmation. If approved, implement
it on a new local round branch with bounded-call regression tests and another
full live run. No provider or spending-limit replacement is proposed.

Rollback: return to this round's fixed-flow implementation on the retained branch.
The proposed backend-only change needs no database migration or irreversible
data operation. Any later API/SSE changes require their own compatibility review.

## 9. GitHub Submission and Remaining Work

The Update 6 local checkpoint was committed as
`c65e6140343d9587dbcf042de00a524649ee14d4` with both author and committer verified
as the user's configured identity, `ZhiouZhu2001`. This updates the local status
recorded at the end of Update 6; that historical record remains unchanged.

Update 6 was not pushed. Update 7 is also local, uncommitted and unpushed; neither
round has upload confirmation. The already published Update 5 branch is retained.
No pull request, main merge, release or deployment was performed.

Remaining work: obtain a decision on the bounded ranking-feedback proposal,
resolve count/reason failures, implement channels, filters and actual HTTP SSE
integration, and pass the complete live gate before considering a main merge.

Proposed title:

`fix: tighten recommendation prompts and capture replayable evaluation evidence`

Proposed description:

Separate channel availability from catalog search subjects and explicitly limit
recommendation proper names to the same book's title/description. Capture version
2 evaluation snapshots, shortlist/ranking input and code fingerprints, and add
offline replay with strict completeness checks. The investigation found that
described-candidate counts do not guarantee enough valid recommendations, and
identifier validation can also reduce the final result count.

Validation: 152 offline tests, scoped lint/formatting and report integrity checks
pass. All 20 live cases ran, but five count checks and four reason heuristics
failed; links and first-book SSE evidence remain blocked. Replay reproduces all
20 verdicts without live calls. Prompt tuning has not resolved the quality gate.

No API, database, frontend or production dependency changes. A bounded ranking
feedback change is documented for approval and has not been implemented. This
branch depends on unpublished Update 6 and unmerged Update 5. See
`update_version/Lumen_Update_Version_7.md` for evidence, compatibility, call-budget
implications and remaining work. Upload and merge confirmation remain pending.
