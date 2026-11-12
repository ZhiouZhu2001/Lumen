# Lumen Update Version 23

## 1. Basic information

- **Round:** 23, an implementation round rather than an application release.
- **Date:** 2026-11-12, Europe/Madrid.
- **Branch:** `codex/update-23-operations-readiness`.
- **Known baseline:** `eecc0919e28b21163d8cd180a081e6b18b550e99`, the verified round-22 checkpoint on local and remote `main`.
- **Objective:** implement the specification's structured search/node diagnostics and prepare concrete deployment and scheduled-backup files for review.
- **Actual scope:** application JSON logging, request/node/model timings and counters, safe warning events, focused tests, an optional PostgreSQL loopback override, inactive deployment/scheduler templates and operator documentation. No public deployment or scheduled production work was performed.
- **Working tree:** the next-round branch was created before implementation. After the interruption, its baseline and clean working tree were checked again; no unrelated user edits were present. The next available update number was 23.
- **Scope:** 24 files, including this record. No files were deleted.

### Completed round-22 merge

The user requested merging round 22 and beginning the next round. The reviewed 19 implementation/test/configuration fingerprints still matched; only the existing update record received submission-status additions. The verified author and committer were `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`.

Automatic review initially rejected the branch push because it required separate upload confirmation under the project rules. No workaround was used. The user then explicitly confirmed the round-22 upload and remote-main synchronization. The 20-file functional scope is commit `9cda284`; approval-status receipts culminate in `eecc091`.

| Checkpoint | Actual result |
| --- | --- |
| Round-22 branch, `eecc091` | [Run 42881932594](https://github.com/ZhiouZhu2001/Lumen/actions/runs/42881932594): Backend, Frontend and Container checks all succeeded. |
| Remote `main`, fast-forwarded to the same checkpoint | [Run 42882721166](https://github.com/ZhiouZhu2001/Lumen/actions/runs/42882721166): the same three jobs all succeeded. |

The remote `main` pointer was subsequently read again and still matched `eecc091`. No pull request, force-push, release or deployment occurred. These receipts complete the pending submission history in the preceding record without rewriting its earlier checkpoints. Round 23 is a separate local scope and has no upload approval.

## 2. Technologies used

No application dependency, primary framework, model provider or bibliographic source was added or replaced.

- **Python standard logging, JSON and dataclasses:** provide one application handler and a small fixed event/field contract without a hosted telemetry service.
- **ContextVar, context managers and asyncio:** isolate request and node measurements while preserving asynchronous graph execution, generator interleaving and cancellation.
- **Existing LangGraph/LangChain interfaces:** wrap the same four fixed nodes and structured model helper without changing prompts, graph routing or model arguments.
- **Existing httpx budget transport:** records a diagnostic attempt only after the existing PostgreSQL reservation succeeds and before the underlying send.
- **pytest, Ruff and Alembic:** verify privacy, timing/counter semantics, concurrency and the unchanged schema using both native Python and isolated Linux containers.
- **Docker Compose, Caddy and PostgreSQL tools:** validate build/runtime behavior, optional loopback access and a real consistent dump/isolated restore using synthetic data.
- **systemd and flock templates:** describe a proposed Linux host job. Syntax/calendar checks ran in a disposable Linux container; no host unit was installed or activated.

## 3. Implementation

### Safe application JSON logging

The API lifespan configures the `app` logger at INFO. Configuration reuses one JSON handler, removes other application handlers and prevents propagation to an unfiltered root handler. Root and third-party HTTP logging are not enabled. A broken output sink does not fail a recommendation or print a raw log record.

The formatter emits only known event identifiers, generated UUIDs, known graph nodes/sources/outcomes/error codes, booleans and valid nonnegative numeric fields. It never interpolates message arguments, formats exception tracebacks or serializes arbitrary extras. Unknown messages become a generic application event. Existing catalog, validation, health, cache and refresh warnings were converted to fixed identifiers instead of raw exceptions, source records or rejected ISBN values.

This is an application-log contract, not a claim that every unrelated service or startup/runtime exception is globally redacted. Production SQL echo remains false, and unreviewed HTTP/access/debug logging should not be enabled.

### Request, node and model measurements

Each admitted recommendation stream creates a private trace using the same `search_id` as its terminal SSE event. Context is bound while advancing or closing the iterator and is restored before yielding a frame to the caller. This avoids retaining a context token across generator yields, including when generators are interleaved in one task or closed from another task.

Each actual graph-node invocation logs its own elapsed wall time, outcome and model counters. Overall progress remains cumulative. Structured model invocations log their duration, including provider-SDK backoff, without inspecting or recording their input/output. The underlying structured-output call and its exception unwrapping remain unchanged.

`model_calls` counts entries into the structured helper. `model_attempts` counts successful pre-send reservations observed after the real daily-budget commit. SDK retries reserve and count again; a rejected reservation counts as zero attempts; a failed send is never refunded. Cached results have zero model calls and attempts. These diagnostics are neither a token/currency meter nor an alternative spending ledger.

The final summary records completed/failed/cancelled processing, cache status, safe error code, wall duration and emitted-card count. An expected empty search is completed with `error_code=no_results`; it is not classified as a provider outage. An emitted card remains provisional until normal persistence/completion, so its count alone proves neither database commit nor browser receipt. Pre-stream HTTP admission denials retain the existing behavior and are outside these stream summaries.

The fixed graph, maximum two broadenings, six logical-call bound, real-candidate checks, author/reading constraints, persistence transaction and database foreign keys are unchanged. Trace fields are not added to graph state, caches, SSE payloads or database rows.

### Deployment and backup preparation

The deployment proposal retains the approved single-VPS architecture, gives an explicitly unapproved capacity-test candidate, states the missing host/domain/budget/retention decisions, compares alternatives and documents activation/recovery/rollback steps. It makes no provider price, capacity guarantee or purchase decision.

The existing host backup tool requires a localhost database URL and Docker CLI, whereas base Compose deliberately publishes no database port. The optional `compose.backup.yml` adds only a PostgreSQL loopback mapping; Redis stays private. It is not automatically included by the base stack. The default port is 5434 and can be changed through `LUMEN_BACKUP_PG_PORT`.

Inactive environment and systemd examples use a fixed project/path, separate model-key-free backup settings, a private state directory, a nonblocking lock and the already verified backup command. The proposed timer is 03:15 UTC with up to ten minutes of jitter and catch-up after downtime. No schedule, off-host copy, encryption key, log rotation or deletion policy was enabled. The actual Linux account, executable paths and Docker privileges still require target-host review.

Example production Caddy mappings retain 80/TCP, 443/TCP and existing 443/UDP. The production environment contains an invalid placeholder domain and password; it is not launch-ready until the operator fills reviewed private values. The current Compose URL interpolation is documented as requiring a high-entropy URL-safe password, rather than silently changing an existing database password or URI format.

## 4. File changes

| File | Change and before/after behavior |
| --- | --- |
| `backend/app/observability.py` | Added: allowlisted JSON formatter/handler, request/node scopes, per-invocation timing and counters. Previously no unified application output contract existed. |
| `backend/app/main.py` | Modified: configure application logging at lifespan startup. |
| `backend/app/search_stream.py` | Modified: isolate per-stream context around iterator execution and emit start/final summaries; public event shapes and processing rules remain unchanged. |
| `backend/app/graph/workflow.py` | Modified: measure the existing four node callables without changing edges or node logic. |
| `backend/app/llm.py` | Modified: measure the existing structured invocation through a private wrapper, preserving model arguments and result checks. |
| `backend/app/usage.py` | Modified: observe successful committed reservations before send; no admission/accounting algorithm change. |
| `backend/app/graph/search.py` | Modified: log a fixed source/status event instead of exception text and URLs. |
| `backend/app/graph/rank.py` | Modified: omit raw rejected model ISBN values from warning output. |
| `backend/app/sources/google_books.py` | Modified: omit invalid provider records and validation details from warnings. |
| `backend/app/sources/open_library.py` | Modified: apply the same fixed source-warning contract. |
| `backend/app/db.py` | Modified: report a safe PostgreSQL health event instead of a raw driver exception. |
| `backend/app/cache.py` | Modified: report a safe Redis health event instead of raw connection details. |
| `backend/app/book_refresh.py` | Modified: remove the book identifier from optional-refresh warnings. |
| `backend/tests/test_observability.py` | Added: 12 meaningful tests for data exclusion, invalid extras, handler configuration, actual graph measurements, concurrency, reservation denial/failure, generator closure/cancellation, cache hits, sink failures and empty searches. |
| `backend/integration_tests/test_cache_usage.py` | Modified: retain existing SDK-retry/budget assertions and additionally verify one logical call versus one/two committed attempts. |
| `compose.backup.yml` | Added: optional PostgreSQL-only loopback host access for the existing backup command. |
| `deploy/production.env.example` | Added: inactive container deployment values with placeholders and explicit safeguards. |
| `deploy/backup.env.example` | Added: inactive separate host-backup settings, with blank model keys. |
| `deploy/lumen-backup.service.example` | Added: inactive private/locked host-backup service proposal. |
| `deploy/lumen-backup.timer.example` | Added: inactive UTC daily timer proposal. |
| `docs/observability.md` | Added: event/counter semantics, privacy boundaries and operational limits. |
| `docs/production-deployment.md` | Added: concrete proposal, prerequisites, alternatives, activation gates and rollback/recovery procedure. |
| `docs/operations.md` | Modified: explain the host-backup access gap and link the new optional setup and logging contract. |
| `update_version/Lumen_Update_Version_23.md` | Added: this round and the verified round-22 merge receipt. |

## 5. Project benefits

Operators can identify the slow or failed node, distinguish structured invocations from charged transport attempts and correlate a stream with its diagnostic events. Logs stop repeating catalog/driver exception payloads, and logging failures do not disrupt recommendations. Explicit iterator scoping prevents concurrent searches from sharing diagnostic identities.

The deployment handoff now explains how the existing backup command can reach the container database without publishing Redis, and provides reviewable scheduler settings instead of claiming that a local backup command already runs daily. Real fixture recovery verifies the access path and preservation of the source allowance.

## 6. Future impact and compatibility

- There is no new public API field/endpoint, database table/migration, dependency, model/catalog provider or recurring service charge.
- The existing PostgreSQL ledger remains authoritative at 100 committed outbound reservations per UTC day; no reset/refund or privacy-constraint relaxation was introduced.
- **Cache effect:** the existing signature hashes backend Python code. Deploying these changes creates a new effective parse/result namespace, so searches may be cold under the unchanged cap. No Redis keys or stored allowance are cleared.
- INFO diagnostics increase local log volume. A concrete bounded log-retention candidate is documented for approval; no logs are shipped or automatically deleted by this round.
- Base Compose still has only Caddy host ports. Applying the optional database mapping later can recreate the PostgreSQL container and interrupt connections; the same project/volume must be preserved.
- Systemd files are Linux operator templates, not a Windows scheduler integration or a working production installation. Off-host protection and an active recovery drill remain necessary before launch.
- Earlier architecture concerns about graph/repository/cache domain coupling and future account/personalization ownership are not solved or expanded into this round.

## 7. Verification

| Check actually performed | Result |
| --- | --- |
| Native complete offline backend suite | **401 passed**; no live model/catalog request. |
| Isolated Linux lint/format and complete offline suite | Passed; **401 tests**, including all 389 earlier cases and 12 new cases. |
| Real isolated PostgreSQL/Redis integration suite | **75 passed**, including actual SDK retry handling against a mocked HTTP transport and the real durable ledger. Together with the offline suite, **476 distinct backend tests** passed. The native repeat is not added again to that total. |
| Fresh migration and model agreement | Passed on the disposable PostgreSQL database. |
| Final Ruff checks | Passed; all 114 checked Python files were already formatted. |
| Actual five-service stack | Both production images built; all five services healthy. Localized pages/assets/API routes, runtime exclusions, controlled proxy identity, hourly denial and durable-budget preservation passed. |
| Synthetic long SSE | Passed at **23.44 ms** for `status` and **65,015.50 ms** for terminal `done`. This is transport evidence, not real first-book timing. |
| Production-image log probe | Seven valid JSON records; terminal SSE, node and summary shared the same UUID. A synthetic logical call reported one call and zero actual model attempts. The private query marker was absent. The container had no network. |
| Actual optional-backup path | A disposable PostgreSQL service used the new loopback override; Redis had no host port. A book, search, result and synthetic budget were archived and restored with matching content fingerprints. Source usage remained **7**; only the recovered copy was blocked. The archive was verified and source state was unchanged. |
| Deployment examples | Rendered example Compose config passed: public example Caddy mappings, private Redis/backend/frontend, loopback-only PostgreSQL, cap 100 and blank API keys. Caddy's HTTPS configuration validated offline without DNS/TLS issuance. No production service was started. |
| Linux service/timer syntax | `systemd-analyze verify` and the UTC calendar check passed in a disposable Linux container. A non-running Docker-unit stub supplied only the dependency for syntax checking. No host unit or timer was installed/enabled. |
| Ownership/cleanup | All owned regression, Compose, restore and probe containers/networks/volumes were removed. Final checks found no remaining round-specific containers. Unrelated services were not operated on. |

### Corrections and limits

The first restricted native targeted test invocation did not complete. It exposed application-handler idempotence with extra capture handlers; configuration was corrected to consistently retain only its JSON handler. That run's two identified Python processes were stopped. Subsequent targeted, complete native and complete Linux runs passed. Early lint issues were corrected without disabling the checks.

The first external image probe ran a script under `/tmp` without the application's module path and failed to import `app`. Its original output remains in `backups/round23-runtime-initial.log`; setting the probe's `PYTHONPATH=/app` produced the successful real-image check, without changing the production entrypoint. Syntax verification initially saw executable bits inherited from a Windows bind mount; temporary installed unit copies were given mode 0644, as documented for deployment, and the final check had no diagnostics. The production-config harness was corrected to account for the existing third 443/UDP mapping; the application mappings were not changed to satisfy it.

No fresh live 20-query quality gate, real first-book latency, provider credential/quota test, production DNS/certificate, capacity test, off-host transfer or active Linux scheduler run was performed. Frontend code is unchanged, so a fresh browser visual sweep/native frontend suite was omitted; the actual frontend image build and container pages/assets were checked. Hosted CI results above belong to the merged round 22; round 23 has not been uploaded and has no hosted result yet.

### Retained evidence

Evidence is Git-ignored under root `backups/`; no database archive or environment credential is submitted:

- `round23-native-unit.xml`: complete native offline result.
- `lumen-round23-regression-b30a893a42/`: archived source, log, two JUnit reports and the successful Linux regression receipt.
- `round23-container-check.json`: actual image IDs, five-service checks and synthetic SSE timings.
- `round23-backup-current.json` and `round23-backup-probe-1d0f8be92f/`: loopback-backup/recovery receipts and the private synthetic archive.
- `round23-runtime.json`, `round23-runtime.log` and `round23-runtime-initial.log`: successful image diagnostics and retained initial probe failure.
- `round23-systemd.json`, `round23-systemd.log`: successful static service/calendar checks.
- `round23-production-config.json`: successful inactive-template validation.
- `round23-verification-manifest.json`: LF-normalized fingerprints for the 23 implementation/configuration/documentation files, evidence hashes and an exact comparison of all **189** archived backend files with the final source. Its SHA-256 is `5c32e68d23cb47390d45076d327fd1c86b26a099ee0055cbe796738913b41b0e`.

## 8. Approvals and remaining work

The user authorized the next local round, and the logging behavior is already required by the specification. No major application architecture, product scope, schema, provider or spending decision was needed. The production files are explicitly proposals; no host purchase, new cost, domain configuration, public release, scheduler activation, retention deletion or off-host data movement was authorized or performed.

Next decisions are the actual host/domain/budget, approved operator access, local log limits, backup schedule, encryption/key custody and off-host retention. The proposal documents the rationale, alternatives, impacts and rollback. After those decisions, validate the actual host, perform the full live bilingual six-check gate and real latency measurement, then obtain the corresponding first-release/deployment approval. Existing archives and the durable ledger must remain protected through any rollback or recovery.

## 9. GitHub submission

**Proposed commit title**

`feat: add safe search telemetry and deployment preparation`

**Proposed commit description**

Lumen logged cumulative graph progress without a unified structured output contract or individual node/model measurements. Add request-local JSON diagnostics with per-node durations, structured-call counts and committed pre-send attempt counts. Exclude raw messages, exception payloads, queries, metadata, URLs and client identities; preserve isolation through concurrent streams, cancellation and cross-task generator closure.

Prepare an optional PostgreSQL-only loopback backup override, inactive production/backup environment and systemd templates, and a deployment proposal with explicit approvals and rollback. Preserve the API/SSE contract, graph/retry limits, candidate validation, schema, providers and authoritative 100-attempt allowance. Backend code signatures can cause cold caches under the existing policy; no new service or paid dependency is introduced.

Validation: 401 offline and 75 real PostgreSQL/Redis tests passed, 476 distinct tests in total; native offline repetition, lint/format and migration/model checks passed. Both images and all five services passed the existing isolated stack checker, including the synthetic 65-second SSE. A no-network image probe verified safe JSON and shared search identity. A synthetic database backup/restore through the new loopback path preserved the source ledger. Inactive Compose/Caddy and Linux unit/calendar syntax checks passed. No live model/catalog request, production deployment, active timer or round-23 hosted CI run occurred.

See `update_version/Lumen_Update_Version_23.md`, `docs/observability.md` and `docs/production-deployment.md` for behavior, evidence, compatibility, decisions and remaining work.

**Actual status:** completed local implementation and verification, uncommitted on `codex/update-23-operations-readiness`. Round 23 is not uploaded or merged. Explicit confirmation of this reviewed 24-file scope is required before a branch push; author/committer identity and submission content must be rechecked before committing. No co-author or tool attribution has been added. Round 22 is already merged and verified on remote `main` as recorded above.

### Submission preparation, 2026-11-12, Europe/Madrid

The user requested merging this round into `main` and starting the next task. All 23 implementation/configuration/documentation fingerprints were rechecked and matched the reviewed manifest; the 24-file scope is unchanged apart from this submission-status addition. Author and committer identities were verified as the project owner's configured identity. Remote `main` still matches the known baseline. The reviewed local commit can be prepared immediately; separate confirmation of this round's GitHub branch upload and remote-main synchronization was requested in accordance with the repository's upload rule and the preceding round's automatic-review requirement. No production deployment or scheduler activation is included.

### Explicit upload confirmation

The functional scope was committed locally as `4b7866574ae50e12b1997b869fb685ec12447d3e`. The user then explicitly confirmed uploading the reviewed round-23 branch and synchronizing remote `main` after successful hosted checks. This confirmation covers this scope and its submission receipts, not the next round's substantive changes, public deployment or timer activation. Hosted results and the final main checkpoint will be recorded in the next round's handoff record after completion.
