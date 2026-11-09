# Lumen Update Version 13

## 1. Basic information

- **Implementation date:** 2026-11-08 (Europe/Madrid); live merge-gate verification continued on 2026-11-09 after the natural allowance reset.
- **Branch:** `codex/update-13-author-constraints`.
- **Baseline:** `5d0c7e0c170e29e877037fa83eff9599339e84cb` on remote `main` and `codex/update-12-cache-and-usage-guards`, verified after the authorized upload/merge.
- **Objective:** enforce explicitly named authors and complete reliable end-to-end stream verification within the approved spending limit.
- **Actual scope:** original author intent, bounded search anchoring, metadata checks at ranking/output/cache/persistence boundaries, proxy-deadline correction, deterministic and live regressions, shared-budget evaluation isolation, documentation and retained evidence.
- **Status:** implementation and required verification completed. The new 20-case six-check frontend gate passed on 2026-11-09. This branch remains local for explicit upload review; no Update 13 push or merge is authorized.

The user explicitly requested merging the previously reviewed work before beginning this repair. Update 11 checkpoint `c2b6d927860ac8430f67eda56962eb4da8f1a501` and Update 12 commit `5d0c7e0c170e29e877037fa83eff9599339e84cb` were uploaded together on the Update 12 branch and fast-forward merged into `main`. Both remote refs were verified at the latter commit. Git author/committer identities were the verified project owner's configuration; no co-author credits, collaborator invitations, pull request, release or production deployment were added.

Initial pushes stalled at account selection in the existing credential manager. Those owned attempts were stopped after verifying their process trees. Selecting the verified project account explicitly for the Git command allowed the existing credential to work noninteractively. No credential was printed, exported, replaced or newly requested. The working tree was clean before this repair branch was created; no unrelated edits were incorporated.

## 2. Technologies used

No new framework, dependency, provider or service was introduced.

- **Existing Pydantic structured output:** the original parse now includes optional `requested_authors`, copied only from the reader's actual words. The default empty list remains compatible with historical captured queries.
- **Unicode normalization and token matching:** compare real catalog author names conservatively across case, accents, punctuation and surname-first notation, without fuzzy alias inference.
- **Existing LangGraph state:** retain the initial author's requirement across both permitted broadening retries, alongside the original genre. No extra model node or call was added.
- **Existing pick validation, SSE, cache and SQLAlchemy repository:** reject wrong-author picks before they can stream or become completed results; reuse the same constraint when validating cached snapshots and persistence.
- **pytest and native PostgreSQL/Redis tests:** exercise the actual captured failure, source/ranking seams, output/cache/storage boundaries and existing transaction behavior.
- **httpx and the existing evaluation reporting utilities:** record two actual supplementary author queries through the running frontend, without treating their public-card checks as the full private-observer gate.
- **Next.js 16.4.2 forwarding configuration:** its supported `experimental.proxyTimeout` setting now covers the existing backend stream deadline.
- **Redis COPY and scoped test resources:** reuse real unexpired cache entries without changing their TTLs; keep hourly test counters separate while using the normal shared daily model budget.
- **Python ctypes/Windows execution state:** temporarily inhibit idle system sleep for the active evaluation process, then restore the prior thread state. This adds no dependency or persistent operating-system setting.

## 3. Diagnosis and implementation

### Reproduced failure

The retained Update 12 request was `Quiero una novela sobre el mar de Toine Heijmans`, with 2010s/short filters. Its three real cards satisfied ISBN, language, description and metadata checks, but two books were by Herman Melville and Hugo Hiriart. The existing final validator accepted the whole snapshot.

A read-only replay first produced a deterministic assertion naming the two unrelated ISBNs: `9788490651261` and `9786077352921`. The three-card evidence was minimized into `backend/tests/fixtures/author_mismatch_update12.json`, preserving real bibliographic metadata and reasons. Two regression tests then failed on the baseline for the exact symptoms: persistence did not reject the snapshot, and the compiled bounded graph retained all three authors after broadening. An initial fixture-copy attempt used a redirected temporary directory and was corrected before the meaningful red tests; missing-fixture failures were not counted as proof of the product bug.

The investigation distinguished missing structured author intent, loss during broadening and missing final/cache checks. The implementation had no durable positive named-author constraint: it relied on query text and model judgment. Those omissions allowed valid ISBNs with the wrong author to pass every later boundary. This is the root cause addressed by the repair.

### Literal original author intent

The existing initial parsing call now emits `requested_authors`. The prompt distinguishes a person's own books from books about them, comparisons, exclusions and nationalities. Cleaning accepts names only when their normalized words occur in the reader's request; it drops invented expansions, generic author/nationality labels and clear nearby comparison/topic/negative references.

The initial cleaned list becomes `request_authors` in graph state. Broadening cannot replace it with a new list or remove it. For a single requested author, every broader catalog query retains that name unless it is already present. This changes catalog query anchoring, not the source APIs or maximum number of searches/retries.

For legacy snapshots without the new field, a narrow fallback recognizes by/de/por attributions to full, literally named authors already present in retrieved catalog metadata. It avoids clear comparison, biography and negative mentions. It is a conservative compatibility guard, not a general natural-language author parser or an author database.

### Catalog metadata enforcement

Candidate eligibility now combines the existing date/page and reader-type checks with author metadata matching. The ranker never receives known unrelated authors for a constrained request. Retained picks are validated against the same eligible set, so a rejected author cannot reenter during a later round. Missing author metadata does not establish a match. If no requested-author book is retrieved, the workflow exhausts the existing bounded retries and does not fill the result with other authors.

Matching uses whole normalized names, not a name mentioned in a title, description or generated reason. Case and diacritics are normalized; single-comma surname-first catalog notation is supported. Coauthor lists match when they contain a requested name. Multiple positive requested names are treated as alternatives; the implementation does not claim to infer a special joint-authorship requirement, pseudonyms, abbreviated-name identity or nationality.

Before any book lookup/emission, the stream revalidates final picks against the author requirement. A malformed graph result fails closed before emitting a wrong-author card. The existing repository validation also checks author identity, which automatically protects completed-cache reads through the same boundary. The source/rule application signature invalidates old parse/result namespaces when this implementation changes; raw catalog payloads can still be parsed under the new rules.

### Saved search history

The original requested names are stored in the existing `searches.parsed_query` JSON even if the last broader query omitted them. No table or migration changed. All existing real-ISBN validation and foreign keys remain active. Wrong-author snapshots fail validation before SQL, leaving no rows. The original failed historical search records and earlier reports were preserved rather than rewritten or deleted.

### Evaluation coverage

The six-check evaluator now also rejects a recommended candidate whose author metadata conflicts with independently declared expected authors or the original retained author requirement. This strengthens identity checking without removing a check or changing the mandatory 20-case coverage, count rules, retry bound or latency limit.

Two supplementary cases live in `backend/evals/author_queries.yaml`. Their runner checks actual wire authors, date/page constraints, counts, ISBN checksums, stream completion and first-book timing. The expected author is declared by the fixture rather than inferred solely from the running parser, so silently losing the constraint cannot create a false pass. The report explicitly sets `full_suite: false` and states that public-card checks do not independently capture candidate membership. These cases do not replace the required 20-case observer gate.

### Stream-boundary correction discovered during verification

The first new full evaluation passed 19 cases; `en_history` had an incomplete HTTP stream and no completed database record. Its original report was retained as a failure. Neighboring saved-search timestamps show an approximately 36,040-second wall-clock gap around that request. This establishes a substantial interruption/time discontinuity, not a normal continuous request duration; the exact cause is not proven and is not attributed solely to the proxy.

A separate deterministic probe then exposed a real forwarding mismatch. Installed Next.js defaults proxy requests to 30 seconds while the backend's search deadline is 60 seconds. A synthetic SSE endpoint emitted a status frame, waited 35 seconds, then emitted done. Direct delivery completed in 35.09 seconds; the frontend closed near 30.03 seconds with `RemoteProtocolError`. No model, catalog or database operation was involved.

The Next.js proxy timeout is now 70 seconds, preserving the backend's 60-second bound and allowing terminal frames to pass. The original 15-second first-book requirement is unchanged. After rebuilding/restarting the frontend, the same probe completed both paths in about 35 seconds. The diagnostic endpoint exists only in the temporary probe process and was not added to the real API.

### Cache-aware retry without a second spending allowance

The retry helper uses an initially empty dedicated Redis database for caches and hourly admission. Only valid current-version parse/result caches and raw catalog entries are copied with their existing TTLs; no IP counters are copied or cleared. The same production usage methods enforce the test environment's 20-search hourly limit, while daily checks and every actual model HTTP attempt directly use the normal shared Redis counter. A native Redis regression proves a normal caller and an isolated evaluation cannot each claim a separate daily allowance.

This avoids repeating already completed model work or overwriting usage to obtain a pass. The final retry started with 13 result-cache hits and 20 parse-cache hits and is explicitly reported as cache-aware. It still executes all 20 real HTTP requests, validates cached snapshots under the repaired backend, captures private candidate evidence, saves new search histories and runs all six required checks. Cold-model performance is not inferred from cached first-book timings.

## 4. File changes

| File | Before/after purpose |
| --- | --- |
| `backend/app/authors.py` | Adds literal-name cleaning, conservative catalog comparison, narrow legacy intent recovery and single-author query anchoring. |
| `backend/app/graph/parse_query.py` | Adds the optional structured author field, its semantic instructions and literal-input validation to the existing parsing call. |
| `backend/app/graph/state.py` | Retains the original named-author list independently of later broader parsed queries. |
| `backend/app/graph/workflow.py` | Anchors single-author searches, excludes other authors before enrichment/ranking and preserves the requirement through retries and retained picks. |
| `backend/app/graph/rank.py` | Adds author checks to the established pick validator and records wrong-author rejection feedback. |
| `backend/app/search_stream.py` | Revalidates final picks before any card lookup/emission, including author metadata. |
| `backend/app/repository.py` | Applies author validation before writes and saves the original author list in the existing parsed-query JSON. Its validator also protects cache reads. |
| `backend/evals/checks.py` | Supports independently declared expected authors and strengthens the existing authenticity outcome while retaining six checks. |
| `backend/evals/author_queries.yaml` | Adds two supplementary English/Spanish exact-author requests without changing the required 20-case suite. |
| `backend/evals/author_run.py` | Adds bounded local HTTP author-specific checks and clearly marks their evidence limitations. |
| `backend/tests/fixtures/author_mismatch_update12.json` | Retains the minimized real wrong-author snapshot and original Spanish bibliographic evidence. |
| `backend/tests/test_author_constraints.py` | Tests the original failure, bounded graph behavior, normalization, missing authors, excluded mentions, cache misses, output rejection and evaluator detection. |
| `backend/integration_tests/test_author_persistence.py` | Tests zero-row rejection and correct original-author persistence against native PostgreSQL. |
| `backend/evals/results/eval-authors-20261108-round13.json` | Retains two actual author-specific frontend HTTP SSE checks with source hashes, full cards and timings. |
| `backend/evals/results/author-persistence-20261108-round13.json` | Retains SQL verification of those searches and the unchanged 100-attempt policy/current usage. |
| `frontend/next.config.ts` | Sets a 70-second proxy timeout instead of the installed 30-second default; routing and backend/first-book deadlines are unchanged. |
| `backend/scripts/check_proxy_stream.py` | Adds a no-AI direct/proxy delayed-SSE regression with a temporary loopback endpoint. |
| `backend/scripts/run_isolated_eval.py` | Adds cache/hourly isolation with direct shared-budget enforcement and process-scoped idle-sleep inhibition. |
| `backend/integration_tests/test_cache_usage.py` | Adds a real Redis regression proving both environments share the daily allowance and retain separate active hourly limits. |
| `backend/evals/results/eval-frontend-20261109-round13.json` | Preserves the first 19-pass/one-blocked full run rather than relabeling it as successful. |
| `backend/evals/results/eval-environment-20261109-round13.json` | Retains natural-reset verification, initially empty required-case parse/results caches and the first run's shared usage of 50/100. |
| `backend/evals/results/eval-interruption-diagnosis-20261109-round13.json` | Retains the wall-clock interruption estimate and separates it from the independently reproduced proxy defect. |
| `backend/evals/results/proxy-stream-before-20261109-round13.json` | Retains the failed 30-second frontend boundary against successful direct delivery. |
| `backend/evals/results/proxy-stream-after-20261109-round13.json` | Retains successful delivery through both paths after the configuration correction. |
| `backend/evals/results/eval-frontend-20261109-round13-final.json` | Retains the passing 20-case cache-aware frontend retry with all wire/candidate evidence. |
| `backend/evals/results/eval-environment-20261109-round13-final.json` | Records cache reuse, active policy scopes, driver/configuration hashes and shared counter movement from 50 to 61. |
| `backend/evals/results/eval-persistence-20261109-round13-final.json` | Verifies all 20 final search records and 113 ordered SQL recommendations, restored normal health and policy settings. |
| `README.md` | Documents author behavior, proxy boundaries, completed verification and conservative identity limits. |
| `CLAUDE.md` | Records original-author and stream-deadline invariants plus truthful cache/isolation reporting. |
| `backend/evals/README.md` | Documents author, proxy and shared-budget isolation commands without weakening the primary suite. |
| `update_version/Lumen_Update_Version_13.md` | Adds the diagnosis, implementation, verified publication baseline, retained failures and completed results. |

No files were deleted. Database models/migrations, dependencies, providers, public request/card formats, frontend rendering components and spending-limit configuration remain unchanged.

## 5. Project benefits

An ISBN can no longer pass the targeted named-author flow merely because it exists and shares the requested topic. Matching happens early enough to avoid spending ranking/retailer work on unrelated authors, and defensive validation prevents later regressions from silently persisting or streaming them. The durable original intent makes a narrower valid subset preferable to unrelated filler.

The retained real failure and independently declared expected names give future changes a specific regression signal. Anonymous search history retains what was actually requested instead of only the final broadened query's interpretation.

The delayed stream probe prevents a successful early frame from hiding a later forwarding cutoff. Budget-aware isolation permits repeatable HTTP verification without clearing real usage or creating extra model allowance.

## 6. Future impact and limitations

- **API:** no incompatible public request/card/stream format changes. `requested_authors` is internal structured state and additive parsed-query JSON, not a new required client field.
- **Database:** no migration. Older parsed-query documents default to an empty author list; captured by/de cases can receive the conservative catalog-based fallback. Historical incorrect recommendations remain historical evidence.
- **Model/provider/cost:** the stack and provider are unchanged. There are still at most six logical calls and two broadenings. No extra author-resolution model call or external author source was introduced. The normal daily cap remains 100 actual attempts, including retries.
- **Caches:** the existing version signature invalidates old parse/results on the source change. No interactive usage keys or historical database rows were cleared to make checks pass.
- **Identity limits:** metadata may omit or abbreviate names. There is no pseudonym/authority-ID lookup, surname-only expansion, nationality verification or complete semantic-intent proof. Multi-name alternatives are not a guarantee of joint authorship. Negative mentions are not converted into positive filters; this change does not implement a general exclusion engine.
- **Proxy compatibility:** the forwarding timeout is configured through the installed Next.js experimental option. Recheck the delayed-SSE probe when upgrading Next.js; the backend's 60-second search limit and 15-second first-book target were not raised.
- **Remaining priorities:** review this verified branch for upload. Catalog refresh, the share/detail UI, public proxy setup and durable Redis-reset budget operations remain separate unfinished work. The full retry's cache conditions must remain visible when discussing performance.

## 7. Verification

| Check | Actual result |
| --- | --- |
| Original captured-state replay before changes | Failed for two unrelated author ISBNs despite existing final validation accepting them. |
| Two initial regression tests against the baseline | Both failed on the intended symptoms: missing persistence rejection and three retained authors. |
| `python -m pytest -q` | **332 passed**, final run 5.26 seconds, offline fixtures/mocks only. |
| `python -m pytest -q integration_tests` | **31 passed**, final run 8.02 seconds, actual local PostgreSQL/Redis with isolated disposable test data, including shared-budget evaluation isolation. |
| Supplementary Spanish live case | **Passed**: one book by Toine Heijmans, retained 2010s/short filters, first book **9,116.14 ms**; two broadenings. |
| Supplementary English live case | **Passed**: five books by Agatha Christie, first book **5,298.65 ms**; no broadening. |
| Native SQL inspection of both live cases | Passed: original names retained in parsed-query JSON, exact wire order persisted, book author metadata matches, and existing foreign keys apply. |
| `npm test`, `npm run lint`, `npm run build` | Six frontend tests passed; lint and the rebuilt production Next.js application passed. Existing Node module-type warnings remain nonfatal. |
| Delayed-SSE probe before correction | Direct status/done completed in 35.09 seconds; frontend lost done near 30.03 seconds. This negative result is retained. |
| Delayed-SSE probe after correction | Direct and frontend status/done both completed near 35 seconds. Zero model/catalog calls and database writes. |
| Final full 20-case frontend gate | **PASS**: all 20 passed authenticity, language, count, links and reason checks; all 18 nonempty cases passed first-book latency, with two expected nonsense exceptions. |
| Final SQL and normal-preview verification | Passed: 20 saved searches and 113 ordered recommendations matched wire ISBNs, ranks and reasons; direct/proxied health and both locales returned 200. |

The supplementary author report remains separate from the full gate. Update 12's earlier gate is not relabeled as evidence for this repair. The new first full run and the final passing retry are both retained, with their differing conditions documented above.

At the supplementary inspection on 2026-11-08, the shared counter was **72/100**. The user explicitly chose to **retain 100 and wait for its natural UTC-day reset**. Redis server time at 00:50 UTC on 2026-11-09 confirmed **0/100**, without clearing a key. The initial full run had no required-case parse/result hits and ended at **50/100**, with 19 passed cases and one interrupted case. The final retry reused 13 completed results and 20 parses and moved the real shared count from **50 to 61/100**, leaving **39** attempts. No setting was increased, no real usage counter was cleared, and no reconciliation or separate daily allowance was needed for this retry.

The final retry returned **113 cards**. Nonempty first-book timings ranged from **9.90 to 11,924.08 ms**, including cached responses; the seven nonempty cases without completed-result hits ranged from **3,451.11 to 11,924.08 ms**. These are actual wire measurements under the disclosed cache conditions, not a claim that every case reran the model. The 13 cache hits include the two nonsense cases. First-run and probe failure evidence was preserved.

The normal preview was restored with the real Redis database and cap of 100. No diagnostic probe route or evaluation usage facade remains in that process. No production/load test, mobile/browser rendering sweep, author authority-database verification or public deployment was performed. The configuration-only frontend correction was verified through its production build and actual direct/proxied HTTP behavior rather than a visual-layout claim.

Final Ruff lint passed, all **90 Python files** passed format checking, and `git diff --check` passed. All **31 changed/new files** passed configured-credential, language and trailing-whitespace review; newly added text passed attribution checks. Original bibliographic names/titles in the two full captures were preserved under the repository's metadata/localization exception. Existing quoted attribution prohibitions in `CLAUDE.md` were distinguished from added credits. The application/evaluation source fingerprints remain the same **49 hashes** as the author-specific verification; the evaluation driver and changed frontend configuration additionally match their explicit SHA-256 values. Normal service health, all 20 SQL searches/113 results and the real shared budget were independently checked in the final persistence report. The temporary diagnostic route returns 404 in the restored normal backend, and native-test schemas/key namespaces were cleaned.

## 8. Approvals and remaining work

The user authorized merging the disclosed Update 11/12 scope and then implementing this author repair. That upload/merge is complete. The repair uses the existing specification and stack; no new major architecture, provider, schema or paid service decision was made.

The user explicitly retained the 100-attempt daily setting and selected evaluation after its natural UTC-day reset. That decision was followed, and the required new 20-case six-check gate is now complete and passed. The proxy correction is a bounded internal forwarding fix; it does not change the graph, source provider, backend deadline, first-book target or spending policy. All negative and passing evidence remains available.

On 2026-11-09, the user explicitly authorized uploading this reviewed round and merging it into main, then starting the next round. This covers author enforcement, the proxy correction and evaluation tools. No pull request, release or production deployment was authorized.

## 9. GitHub submission

**Proposed commit title**

`fix: enforce named authors and preserve complete search streams`

**Proposed commit description**

A request for a named author's books could return real books by unrelated authors, and the frontend's default 30-second forwarding timeout could cut off a valid stream before the backend's 60-second deadline. Preserve literal original author intent, anchor single-author catalog queries, enforce retrieved author metadata through ranking/output/cache/persistence, and allow the backend's terminal SSE frames through a 70-second proxy boundary.

Add captured-failure and independent-author regressions, native storage/shared-budget checks, a deterministic delayed-stream probe and cache-aware evaluation isolation. Preserve the graph, two-retry/six-logical-call limits, ISBN/foreign-key defenses, providers, public API, 15-second first-book target and 100-attempt daily cap. No migrations or dependencies are added.

Validation: 332 offline tests, 31 native PostgreSQL/Redis tests, six frontend tests, lint and the production frontend build passed. Two real author-specific queries passed. A failed initial full run and negative proxy probe are preserved. The corrected 35-second probe passed both paths, and the final 20-case frontend gate passed all applicable six checks with 113 cards and 20 verified saved searches. The retry reused 13 completed results and 20 parses; it is not presented as fully cold. All real attempts used the normal shared budget, ending at 61/100 after the natural daily reset. Identity, semantic and production-readiness limitations remain documented.

See `update_version/Lumen_Update_Version_13.md` for the reproduced cause, actual scope, retained live reports, compatibility and remaining work.

**Actual status:** Update 11/12 were uploaded and merged into remote `main` at the verified baseline above. The user explicitly authorized the reviewed Update 13 upload and main merge on 2026-11-09. At record preparation, the verified changes are being committed for that authorized submission; the next round will record the resulting verified commit. No pull request, release or production deployment is authorized or claimed.
