# Lumen Update Version 21

## 1. Basic information

- **Round:** 21, an implementation round rather than an application release.
- **Date:** 2026-11-10, Europe/Madrid.
- **Branch:** `codex/update-21-runtime-readiness`.
- **Known baseline:** local-only round-20 checkpoint `1da9329c9abcaa64bddb6f2e96dd490ad4c7b52d` on `codex/update-20-container-ci`.
- **Published baseline:** local `main` and its known tracking checkpoint remain at round 19, `3e28cac0514e4aefe53342b9a43885ca09ce1c38`. No round-20 or round-21 upload or merge was performed.
- **Objective:** provide an explicit read-only operator check for local AI runtime prerequisites beyond dependency connectivity.
- **Actual scope:** a readiness command, explicit inclusion in the backend image, failure/privacy/resource-cleanup tests, real database read-only verification, container command checks and documentation. Public endpoints, application behavior, migrations, providers and spending constraints are unchanged.

### Pending-round dependency

The user requested leaving round 20 unmerged and starting the next round. Before implementation, its reviewed 11-file scope and verification hashes were checked, and author/committer identities were verified as `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`. Round 20 was saved as the local commit above with its prepared English description and no co-author/tool attribution. The new branch was created from that clean checkpoint. This preserves two coherent scopes; it does not grant upload approval for either round. The earlier round-20 uncommitted checkpoint remains historical, and its local-checkpoint appendix records this sequencing.

## 2. Technologies used

No new dependency, framework, provider, database table or external service was introduced.

- **Python/asyncio:** a small operator command runs independent migration/Redis checks concurrently and bounds each database, Redis and budget component to two seconds.
- **Alembic:** reads the packaged migration heads without executing migration functions; compares them with the database revision marker.
- **SQLAlchemy:** reads the existing Alembic version table and existing daily ledger. A separate table descriptor describes `alembic_version`; it is not registered with application models and creates no runtime schema.
- **Redis:** PING checks connectivity without cache/IP writes.
- **Existing DailyBudget.snapshot:** reads the server-clock-based current-day allowance without consuming a reservation, advancing an old row or changing its floor.
- **Docker:** explicitly copies the command into the existing non-root backend image; actual CLI execution is tested in disposable Linux containers.
- **pytest and Ruff:** verify operator states, bounded failures, safe output, owned resource closure and actual database/cache preservation.

## 3. Implementation

### Separate local readiness from health

The existing `/api/health` correctly measures PostgreSQL and Redis connectivity. A new installation can therefore be healthy while its daily ledger remains intentionally uninitialized or its model key is absent. The new `scripts.check_runtime_readiness` command reports these additional local prerequisites without changing the API or health policy.

Run `uv run python -m scripts.check_runtime_readiness` from `backend/`, or `docker compose exec -T backend python -m scripts.check_runtime_readiness` for a running stack. It prints JSON and exits with 0 for `ready`, 2 for `cached_only`, or 1 for `not_ready`. This is an optional operator diagnostic, not a new automatic startup or container-health gate.

`ready` requires matching packaged/database migration markers, Redis connectivity, a configured cap of 100, nonblank model name/key and a known allowance with room. `cached_only` requires the other local prerequisites but a known exhausted allowance; an eligible cached result is not guaranteed to exist. Other missing, unavailable or unknown prerequisites produce `not_ready` and issue codes. A missing model key can still allow a specific cached/legacy request, but the intended uncached AI configuration is not ready.

### Bounded reads and preserved accounting

Migration and Redis checks run concurrently. The budget is inspected only if migration markers match. Missing/future-dated ledger state is unknown and requires operator review; it is never treated as zero. The existing snapshot reader can report logical zero after the UTC day changes while preserving the actual older row. Daily exhaustion is reported rather than repaired. A changed cap is a configuration issue; the command never sets it back or raises it.

The command performs SQL reads and Redis PING only. It does not apply migrations, initialize/import/block a budget, reserve/refund attempts, clear keys or write searches/IP history. The public three-endpoint API, fixed graph and real-book safeguards remain unchanged.

### Safe output and lifecycle

Model configuration is checked for presence only. The report includes booleans, safe statuses, migration IDs and budget totals/date; it never prints key values or connection URLs. Remote credentials are always marked unverified. The command disables SQL echo for its own engine and sanitizes validation/driver setup errors to their type rather than including credential-bearing messages.

The engine and Redis client are owned and closed by the wrapper. Cleanup still disposes the engine when Redis construction or Redis cleanup fails. Component timeouts cancel slow checks. The existing health checks remain unchanged because expected daily exhaustion is not a reason to classify a running service as unhealthy.

### Image and operational boundaries

The Docker allowlist and explicit copy add only this operator script alongside the existing budget tool. Container transport probes/tests remain excluded. The script reads the existing packaged Alembic metadata; no application dependency, image base, public configuration format or migration changes.

Local readiness does not establish provider authentication/quota, source availability, complete database integrity, recommendation quality/latency, DNS/TLS, production client identity, backup recovery or launch approval. Production backup scheduling/off-host policy remains separate. The command is useful after verified setup or recovery, but cannot replace those procedures.

## 4. File changes

| File | Change and before/after behavior |
| --- | --- |
| `backend/scripts/check_runtime_readiness.py` | Adds the read-only local-prerequisite diagnostic and explicit exit states; no equivalent operator command existed. |
| `backend/Dockerfile` | Explicitly includes the readiness command while retaining the same image/dependencies, non-root user and normal startup. |
| `backend/.dockerignore` | Allows that one additional runtime operator script; other test/diagnostic scripts remain excluded. |
| `backend/tests/test_runtime_readiness.py` | Adds seven unit cases for state/exit mapping, sanitized errors, timeout cancellation and owned-resource cleanup failures. |
| `backend/integration_tests/test_runtime_readiness.py` | Adds eleven real PostgreSQL/Redis cases and compares usage rows/Redis keys before and after inspection. |
| `README.md` | Documents the native/container command and its readiness/remote-validation boundary. |
| `docs/operations.md` | Explains all states, issue handling, read-only semantics and the distinction from health, initialization and recovery. |
| `docs/containers.md` | Adds a post-start operator check and documents the additional explicit image command. |
| `backend/evals/results/runtime-readiness-container-20261110-round21.json` | Retains actual CLI exits, direct fixture fingerprints, image IDs and the successful five-service/streaming check. |
| `backend/evals/results/runtime-readiness-verification-20261110-round21.json` | Retains complete-suite totals, JUnit/log/source hashes, isolation/cleanup results and pending-branch status. |
| `update_version/Lumen_Update_Version_21.md` | Adds this implementation, dependency, verification and submission record. |

This round has **11 files: 5 modified and 6 added**, with no deletions. Round-20 changes are the explicit local baseline, not part of this round's diff. No production app, migration, dependency lock, Compose/Caddy, frontend or workflow definition changed.

## 5. Project benefits

Operators can distinguish dependency connectivity from actual local prerequisites for new AI work. Unknown accounting cannot be mistaken for a fresh allowance, while normal exhaustion receives a clear cached-only status. A safe read-only command can be run after initialization, recovery or a maintenance response without paying for a diagnostic model call or changing data. Distinct exit codes support future operator tooling without changing the product API.

## 6. Future impact

- No API/schema/data migration or application compatibility change occurs. Existing health, admission, cache and daily-attempt behavior are unchanged.
- The backend image gains a small optional command; its startup, base image, user and dependency locks are unchanged. Application cache signatures do not change because app source/rules are unchanged.
- Operators must interpret exit 2 as known exhaustion, not a service crash. The command is intentionally not wired into Docker health or restart policy.
- The model checks establish presence, not validity. The migration check establishes marker agreement, not all table contents or physical integrity. Existing live evaluation, migration/model and recovery checks retain their separate roles.
- Both rounds remain local dependencies awaiting their own reviewed upload/merge authorization. Hosted verification of the round-20 Container checks job remains pending.
- Public release, actual host verification, paid services, backup scheduling/encryption/off-host retention and later UI/media polish remain separate work.

## 7. Verification

| Check actually performed | Actual result |
| --- | --- |
| Full isolated Linux offline suite | **389 passed**, zero failures/errors/skips; pytest console duration **5.66 seconds**. Includes seven new unit cases. |
| Full isolated PostgreSQL/Redis suite | **75 passed**, zero failures/errors/skips; pytest console duration **28.90 seconds**. Includes eleven new readiness cases and the existing historical 20-case persistence replay. |
| Total fresh backend tests | **464 passed**. New tests are included, not counted again. |
| Ruff lint/format | Passed; **112 Python files** formatted correctly. |
| Fresh migrations/model agreement | Both existing migrations applied to temporary storage; no new upgrade operations detected. |
| Eleven readiness integration states | Healthy setup, empty/future/exhausted/older-day ledger, missing/blank key, changed cap and older/empty/missing migration markers returned the expected states. All compared usage rows and Redis keys were unchanged. |
| Actual CLI in the new non-root image | Seven cases passed: missing ledger, remaining budget, missing key, changed cap, exhaustion, Redis outage and budget preservation after Redis loss. Exit codes 0/1/2 matched the reports. |
| Direct container fingerprints | Five separate-fixture CLI cases had equal before/after budget fingerprints. The other two CLI cases were not separately fingerprinted; their report field is null, not a detected change. Corresponding read-only states are also covered by integration tests. |
| Rebuilt images/full stack | Both actual images built, all five services healthy, localized/static/API checks and controlled hourly admission passed. |
| Redis loss/restart and forwarding | Durable test budget remained enforced; all synthetic forwarded identities resolved correctly. |
| Separate synthetic delayed SSE | Status at **34.29 ms**, done at **65,029.28 ms**, after 65 seconds of silence, with the existing headers and no compression. No real first-book result is claimed. |
| Test isolation and cleanup | Unique schemas/key namespaces cleaned; temporary public test ledger remained uninitialized in the suite database. Dedicated test containers/networks/volumes were removed after ownership checks. |
| Normal environment/main preservation | All three normal Lumen container states and start times unchanged. `main` stayed at `3e28cac`; no normal database/allowance reset or upload was performed. |
| Evidence/source agreement | The 222-file backend/frontend test archive and final source hashes matched. Complete logs/JUnit files remain in the ignored private check directory; public receipts retain their hashes and sanitized outcomes. |

The real CLI fixture database was separately created/migrated, then raised to synthetic floors 7 and 100 through the existing admin tool. These setup writes were separate from the read-only command, and no ledger was lowered. A placeholder model key exercised presence checks without remote authentication. Five direct CLI fingerprints were equal; null comparison entries clearly identify the two cases without separate fingerprints.

The first restricted Windows unit invocation did not produce test results and was stopped; only its two identified processes were terminated. Successful totals above come from the full isolated Linux runs, not that invocation. No test was relaxed or failure hidden. Container orchestration ran on Windows against actual Linux images; an Ubuntu-hosted result is not claimed.

No fresh live model/catalog recommendation gate, browser visual sweep or separate frontend native suite was run: prompts, retrieval and frontend source are unchanged. Frontend compilation remains included in the actual image build. There were no real model/catalog requests, changes to the 100-attempt cap, GitHub uploads or public deployment.

## 8. Approvals and remaining work

The user explicitly requested keeping the preceding branch unmerged and continuing. The local-only checkpoint preserves that instruction and avoids mixing pending changes. The new operator command is a reversible implementation within existing runtime/operational requirements; no major architecture, provider, product capability, schema, privacy or spending decision was required.

Round 20 is committed locally as `1da9329`; round 21 remains uncommitted on its dependent branch. Neither is uploaded or merged. Their future submission must identify both scopes and receive explicit upload approval; main merges, releases and production deployment remain separate authorizations. Actual production backup, host and retention choices remain unresolved rather than being silently selected by this diagnostic.

## 9. GitHub submission

**Proposed commit title**

`feat: add read-only runtime readiness diagnostics`

**Proposed commit description**

Connectivity health can pass before Lumen's verified daily ledger or model configuration is ready. Add a separate operator command that reads migration markers, Redis connectivity, model configuration presence and the existing current-day budget. Return explicit ready, cached_only and not_ready states with exit codes 0, 2 and 1, bounded checks and sanitized output.

Use the existing read-only budget snapshot without reservations, initialization, refunds, cache/IP writes or remote provider calls. Include the command explicitly in the non-root backend image and document its limits after setup/recovery. Preserve the public health/API behavior, schema, dependency locks, graph, providers and 100-attempt cap. Readiness is local prerequisite evidence, not provider authentication or launch approval.

Validation: 389 offline and 75 PostgreSQL/Redis tests passed, 464 in total, including seven new unit and eleven read-only integration cases. Ruff lint/format and fresh migration/model checks passed. Actual image CLI cases returned all three expected exit states, five direct fixture fingerprints were unchanged, and the full five-service check retained budget/identity protections. A synthetic 65-second stream completed at 34.29 ms and 65,029.28 ms. Three normal services, normal data boundaries and main were preserved; owned test resources were removed. No live recommendation gate or hosted verification is claimed.

See `update_version/Lumen_Update_Version_21.md`, `docs/operations.md` and the two runtime-readiness verification receipts. This branch depends on the separately retained local round-20 commit `1da9329`; neither pending scope is uploaded or merged.

**Actual status:** completed local implementation and verification, uncommitted on `codex/update-21-runtime-readiness`. No round-21 upload approval, commit, push, pull request, merge, release or deployment occurred. Round 20 remains a local-only dependency. Author/committer identity must be reverified before any later commit, and no co-author or tool attribution may be added.

### Combined submission authorization, 2026-11-10, Europe/Madrid

The user subsequently requested merging into `main` and an estimate of remaining work. The current round depends on local round 20, so the necessary combined submission includes their separately reviewed scopes and separate functional commits. The configured author and committer were reverified as `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`. Remote `main` was fetched and still matched the known round-19 checkpoint. Both branches will be uploaded and their three hosted checks inspected before the main merge. No pull request, release, public deployment or new paid service is authorized by this operation. The preceding local-only status records its historical checkpoint; actual upload/check outcomes follow when known.

### Verified branch-upload receipt

The authorized combined submission has uploaded both functional checkpoints without merging either one early:

| Uploaded checkpoint | Actual hosted result |
| --- | --- |
| Round 20, `1da9329c9abcaa64bddb6f2e96dd490ad4c7b52d` | [Run 42849403912](https://github.com/ZhiouZhu2001/Lumen/actions/runs/42849403912): Backend checks, Frontend checks and Container checks all completed successfully. |
| Round 21, `54a2bf8223df2a0da1b3be42245a26d88b61a010` | [Run 42849404647](https://github.com/ZhiouZhu2001/Lumen/actions/runs/42849404647): Backend checks, Frontend checks and Container checks all completed successfully. |

The new container job has therefore now passed on actual Ubuntu-hosted runners for both branches. Earlier statements that hosted verification was pending describe the local checkpoints before this submission. Author and committer identities remain the project owner's verified configuration; no co-author or tool attribution was added.

This receipt is a documentation-only completion of round 21 and introduces no runtime, dependency, schema, spending or evaluation change. At its preparation, the authorized fast-forward main merge is the next operation; the final main revision and main-check outcome are reported after execution. No pull request, production release or deployment is included.
