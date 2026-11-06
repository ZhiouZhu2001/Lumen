# Lumen_Update_Version_5

Date: 2026-11-05 (Europe/Madrid)

Branch: `codex/update-5-search-workflow`

Baseline: `7d05697`, the Update 4 commit merged into `main`.

Objective: Complete the bounded AI recommendation workflow, correct cross-round candidate merging, distinguish no results from service failures, and verify the graph with offline tests and one live query.

## 1. Completed Scope

The compiled graph now runs query parsing, bibliographic retrieval and merging, conditional search broadening, and ranking with recommendation reasons. It keeps one conditional routing point and permits at most two broadening attempts.

This round extends the existing untracked teaching versions of `workflow.py` and `try_graph.py`. It also updates the route tests that already had an uncommitted whitespace change. The working tree was inspected before implementation, and unrelated files were preserved.

The browser endpoint, database persistence, SSE transport, bookstore channels, filters, caching, and rate limiting remain outside this round. The existing web endpoint still uses its keyword/JSON workflow.

## 2. Technologies Used

- **LangGraph StateGraph:** Registers the existing parsing, search, broadening, and ranking functions as state-updating nodes. Conditional edges use `route_after_search` to choose ranking, another broadening attempt, or termination.
- **LangChain structured output and Pydantic:** Preserve typed query and recommendation responses. Schema-setup failures, invocation failures, and unexpected response types are classified as model failures.
- **Async httpx:** Reuses the caller-owned HTTP client for parallel bibliographic requests. The graph does not create a new client for every node or put resource objects in search state.
- **ISBN-keyed merging and source-set normalization:** Retains candidate order and existing metadata while allowing later rounds to fill missing fields. Source labels are combined in stable order without repetition.
- **pytest, AsyncMock, and httpx.MockTransport:** Exercise real compiled graphs and node functions with scripted model responses, controlled normalized candidates, and existing recorded HTTP fixtures. Offline tests do not call real external services.
- **Ruff:** Checks backend imports and code style and formats the files touched by this round.
- **argparse and a monotonic timer:** Provide a reusable terminal runner with query/language arguments, input validation, elapsed workflow time, and distinct outcome messages.

No new runtime dependency, model provider, bibliographic service, or database migration was introduced.

## 3. Detailed Implementation

### Graph and Bounded Retry Flow

The graph follows `START -> parse_query -> search`. After search, the existing routing function decides between `rank_and_explain`, `broaden`, and `END`. Broadening returns to search, and ranking terminates the graph.

The candidate threshold changes from 10 to 5 usable descriptions to match the specification's five-book decision boundary. Missing, empty, and whitespace-only descriptions do not count. Ranking still receives at most 30 candidates and keeps at most 10 valid recommendations.

Only the broadening node increments `retries`. Both unsuccessful broadening output and repeated searches consume a broadening attempt, keeping the loop finite. Already tried searches are excluded case-insensitively before calling sources. An empty search list returns normally without making HTTP requests or being misclassified as an upstream outage.

Candidate lists accumulate across rounds. The original query is retained, the latest parsed searches replace `parsed`, and `tried` records searches actually attempted.

### Cross-Round Merge Corrections

The previous merge treated an already seen source as a reason to skip field completion. It could also append combined source strings repeatedly across rounds.

The updated merge tracks duplicate records within the incoming batch separately from accumulated history. A later round from the same source can fill missing metadata, including a whitespace-only description. Existing populated fields and the primary title remain unchanged. Combined source names are deduplicated in stable order. Input candidate objects are not mutated.

### No Results and Failure Semantics

- A successful graph with no usable candidates or a valid empty ranking answer returns an empty `picks` list. The terminal runner labels this outcome `no_results`.
- A model exception, unsupported structured-output setup, or wrong structured-response type raises `LLMError`, reported as `llm_failed` by the runner.
- A nonempty ranking response whose entries are all invalid still raises `LLMError`; invented ISBNs must not be treated as a successful recommendation.
- If all source requests in a retrieval round fail, `UpstreamUnavailable` propagates and the runner reports `upstream_unavailable`. A single failed source does not discard successful responses from the other source.

The ranking prompt and output-field description now explicitly allow an empty list when no candidates fit. Other ISBN filtering, reason cleanup, deduplication, and rank assignment remain in code.

### Terminal Runner

The runner accepts `--query` and `--language`, enforces a 3-300 character trimmed query, prints searches, candidate counts, retry count, workflow duration, and final recommendations with reasons. It reports normal no-results outcomes without a failure exit code and uses a nonzero exit code for source/model failures.

Example from the repository's backend directory:

```powershell
Set-Location F:\AI_Roadmap_2026\Lumen\backend
.\.venv\Scripts\python.exe -m scripts.try_graph --query "fantasy with dragons" --language en
```

This command uses the existing configured live services.

## 4. File Changes

| File | Change |
| --- | --- |
| `backend/app/graph/workflow.py` | Completed the pre-existing untracked two-node graph with broadening, ranking, conditional routing, and tried-search filtering; added the compiled return type |
| `backend/app/graph/state.py` | Changed the rankable-candidate threshold from 10 to 5 while retaining the two-retry cap |
| `backend/app/graph/rank.py` | Excluded whitespace descriptions and distinguished valid empty picks from invalid nonempty output; clarified the structured-output contract |
| `backend/app/graph/search.py` | Returned an empty result for an empty search list without making requests |
| `backend/app/sources/merge.py` | Fixed repeated source labels and same-source cross-round metadata completion while preserving incoming duplicate precedence |
| `backend/app/llm.py` | Included structured-output setup in the existing model-error boundary |
| `backend/scripts/try_graph.py` | Extended the pre-existing untracked runner with CLI arguments, outcomes, timing, and actual recommendation output |
| `backend/tests/test_workflow.py` | Added compiled-graph tests for successful ranking, retry bounds, accumulation, invalid picks, empty outcomes, model errors, source failures, and streamed node updates |
| `backend/tests/test_merge.py` | Added regressions for source-label accumulation, same-source field completion, and duplicate-record precedence |
| `backend/tests/test_rank.py` | Added whitespace-only descriptions to the existing shortlist exclusion case |
| `backend/tests/test_route.py` | Added explicit four/five/nine-book boundary cases and a whitespace-description case; normalized existing trailing whitespace |
| `backend/tests/test_search_candidates.py` | Added the empty-search/no-request/no-outage regression |
| `update_version/Lumen_Update_Version_5.md` | Recorded this round's implementation, validation evidence, limitations, and proposed submission |

## 5. Project Benefits

The previously separate AI functions can now run as one bounded workflow. Repeated searches avoid extra bibliographic calls, retries retain useful candidates, and later metadata can make an earlier candidate eligible for ranking.

Explicit empty-result semantics prevent a legitimate lack of matches from looking like an infrastructure failure. The original candidate-only recommendation rule remains enforced independently of model instructions.

The compiled graph and verified node-update stream provide a foundation for later API/SSE integration without changing model or HTTP-client ownership.

## 6. Verification Results

### Offline Checks

- `python -m pytest -q -p no:cacheprovider`: **101 passed**, compared with 72 tests before this round. Final run: 2.11 seconds.
- `ruff check app tests scripts`: **passed**.
- `ruff format --check` for all 12 touched Python files: **passed**.
- `git diff --check`: **passed**.
- Manual runner `--help`: **passed** without making API requests.
- Manual runner `--query ab`: rejected before contacting services with the expected argument-error exit code 2.

Graph tests cover English/Spanish state, immediate ranking, stopping after the first successful broadening, accumulation through two retries, fewer candidates after retry exhaustion, missing/blank descriptions, repeated broadened searches, successful empty catalogs, empty picks, invented ISBNs, model failures at each model stage, unsupported structured output, wrong output types, complete source outage, and partial source outages using recorded responses. Streamed updates were also checked through the retry branch.

### One Live-Service Smoke Check

Used the project's existing configuration for the Spanish request `quiero una novela triste sobre el mar` with a 90-second outer limit:

| Observation | Result |
| --- | --- |
| Searches | `novela mar`, `novela naufragio`, `novela pescadores` |
| Merged candidates | 51 |
| Eligible shortlist | 14 |
| Broadening retries | 0 |
| Recommendations | 5 |
| Measured workflow duration | 6.74 seconds |
| Exit status | 0 |

The selected ISBNs were checked against retrieved candidates by the production ranking logic. This is one live integration observation, not a guarantee of latency across queries or the first-book SSE metric. The API/SSE layer is not connected yet.

## 7. Future Impact and Known Limits

- The candidate threshold now triggers ranking at five usable descriptions, which can reduce broadening calls. The quality/latency tradeoff still needs the planned bilingual evaluation set.
- Open Library search results still lack descriptions. If Google Books is unavailable and no descriptions can be obtained, candidates can exist while the workflow correctly returns no recommendations rather than inventing reasons.
- Recommendation relevance and grounding remain quality-evaluation work. The smoke response included looser thematic matches, such as a river-centered story for a sea-focused request; a five-book response alone does not establish semantic quality.
- Empty picks are a normal graph outcome; the future API adapter must map them to `no_results` and map the existing exceptions to their respective error codes.
- No API request/response contract, database schema, frontend behavior, cache, rate limit, or deployment setup changed in this round.
- The specification's 20-query, six-check `make eval` suite is not present yet and was not run. **The required evaluation gate remains open before merging these prompt/retrieval changes, unless the user explicitly approves an exception.**

## 8. Approvals and Remaining Work

The user approved the Update 5 implementation plan and explicitly instructed implementation to begin. The changes stay within that scope and the existing stack; no additional major technical decision was introduced.

Publication follow-up (2026-11-06): the user explicitly authorized uploading this branch, then chose to retain the branch and complete the full evaluation before merging. Upload is approved; merging into `main` is deferred. The next round will establish and run the 20-query evaluation rather than proceeding directly to persistence.

Status at commit preparation: implementation and verification complete locally; upload approved and initial push pending. Remote publication will be checked after pushing. No PR or merge is authorized until the evaluation requirement has been addressed.

Later rounds will connect persistence and the browser/API stream and complete channels, filters, cost safeguards, and full product evaluation.

## 9. Proposed GitHub Submission

Suggested title: `feat: complete the bounded book recommendation workflow`

Description:

Connect query parsing, bibliographic retrieval, bounded broadening, and ranking in a compiled LangGraph workflow. Rank once five candidates have usable descriptions, retain candidates across at most two broadening attempts, and skip previously tried searches.

Fix repeated source labels and same-source metadata completion across retrieval rounds. Treat a valid empty model answer as no results while preserving separate model and upstream failure paths. Add an English terminal runner with query/language arguments, final recommendations, timing, and clear outcomes.

Validation: 101 offline tests pass, Ruff lint and scoped format checks pass, and a live Spanish query returned five candidate-validated recommendations from 51 retrieved books in 6.74 seconds. CLI help and invalid-query checks also passed. See `update_version/Lumen_Update_Version_5.md` for implementation details and known limits.

Impact: no new runtime dependency, API migration, database change, or frontend change. Full bilingual quality evaluation and API/SSE integration remain pending; the specification's evaluation gate must be satisfied before merging the prompt/retrieval changes.
