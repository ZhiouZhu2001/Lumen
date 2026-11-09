# Lumen Update Version 17

## 1. Basic information

- **Round/date:** 17; 2026-11-09, Europe/Madrid.
- **Branch:** `codex/update-17-durable-budget-and-backups`.
- **Baseline:** `b91eb442de99ed5795ef517dad55d2a186649662`, Update 16 on verified remote main.
- **Objective:** preserve the approved daily 100-attempt allowance across Redis loss and provide private, verified application backups/recovery procedures.
- **Actual scope:** one operational singleton table, atomic durable reservations, paused-service administration, shared live-tool protection, application-schema backup/restore verification, tests, retained evidence and documentation.

Update 16 was uploaded and its actual [branch CI run](https://github.com/ZhiouZhu2001/Lumen/actions/runs/42687930192) passed both jobs before the authorized fast-forward merge. The [main CI run](https://github.com/ZhiouZhu2001/Lumen/actions/runs/42688374029) also passed. Both remote refs matched the baseline above. The verified project owner was the only Git author/committer. No additional credits, collaborators, pull request, release or public deployment were created.

The tree was clean before this branch. All changes here belong to this round. The user subsequently instructed keeping this round local while completing the next round, then handling the two rounds together. No Update 17 upload/main merge has occurred at record preparation.

## 2. Technologies used

No new dependency, primary stack, model provider or paid service was introduced.

- **Existing PostgreSQL/SQLAlchemy/Alembic:** add `ai_daily_usage` with one row (`id=1`, UTC day, nonnegative attempts). Conditional updates serialize concurrent reservations. A committed reservation precedes the provider send. The [PostgreSQL documentation](https://www.postgresql.org/docs/17/sql-insert.html) informed conflict-safe floor administration.
- **Existing Redis:** retain expiring hourly IP admission and caches; it is no longer authoritative for daily model use. No IP/query is copied into the new table.
- **Existing httpx/model wrappers:** retain transport-level accounting for every SDK retry and propagate safeguard errors. Live teaching tools now own/close budgeted clients against the same PostgreSQL ledger.
- **PostgreSQL pg_dump/pg_restore and exported snapshots:** produce compressed custom-format public-schema archives, compare a restored copy against the same consistent snapshot and quarantine recovered budget state. See [pg_dump](https://www.postgresql.org/docs/17/app-pgdump.html) and [pg_restore](https://www.postgresql.org/docs/17/app-pgrestore.html).
- **Docker:** use a newly created, labeled, network-disabled recovery container with no published port. Ownership checks limit cleanup to that target and its anonymous volume.
- **Existing Python/Windows APIs:** protect backup directories for the current owner/SYSTEM on Windows; use 0700 directories and 0600 files on Unix. Archives/receipts remain private and Git-ignored.
- **Existing pytest/Ruff and isolated Linux services:** verify concurrency, retries, clock transitions, unavailable storage, explicit import/rollback and Redis replacement without real model calls.

## 3. Implementation

### Durable daily allowance

`DailyBudget` reads the PostgreSQL UTC clock and atomically updates the singleton only if the current allowance permits another reservation. Concurrent workers share this row. SDK retries reserve separately, failures are not refunded, and an acknowledged commit precedes the outbound HTTP attempt. A crash after reservation can conservatively overcount; it cannot grant an extra request.

The live table keeps only the current aggregate, not daily history or per-request identities. At natural UTC rollover its day advances and the new day's count starts with the first reservation. Missing/future-dated state and SQL failures stop new model work. No automatic missing-row initialization or Redis fallback can silently restore an allowance.

`UsageGuards` retains the existing hourly Redis policy and explicitly delegates daily operations to the durable guard. API workers, isolated evaluations and the five provided live teaching scripts share that same database ledger. The factory requires an explicit budgeted client; supplied diagnostic contexts close clients/engines even on failure. Search prompts, ranking, retrieval parameters, retry limits and public response shapes are unchanged.

### Explicit initialization and rollback

The user explicitly approved the PostgreSQL singleton and retained 100 attempts/day. The new migration creates an empty table. The administration tool requires acknowledgement that all AI workers are stopped. It supports verified initial floors, legacy import, conservative blocking and exporting a floor for an older worker.

Import checks the Redis/PostgreSQL UTC dates and copies known legacy use without clearing keys. A missing legacy key is unknown use and blocks the day at the cap. Current-day floor updates use the greater existing/requested value and cannot lower use. Rollback export likewise preserves the greater Redis/PostgreSQL count and UTC expiry. Migration downgrade refuses to discard the ledger; the runbook explains retaining the schema and avoiding an outdated migration runner during an application rollback.

### Backups and guarded recovery

The backup command verifies that the configured local database and Compose source are the same cluster. A read-only repeatable-read transaction exports the snapshot used by pg_dump and the per-table fingerprints. Only the public application schema is in scope; role/cluster and unrelated-schema backups are not claimed.

Each archive has a unique filename and cannot overwrite another. A fresh offline container restores it. The tool checks that its default public schema is empty before removing that empty schema without `CASCADE`; populated targets are rejected. Restored row counts and ordered content hashes must equal the source snapshot. Only after that comparison, recovered usage is blocked for the current day pending reconciliation or natural reset. Existing databases are never restore targets.

Archives contain stored reader requests and are compressed, not encrypted. They stay in an owner-restricted, Git-ignored directory. No automatic retention deletion, operating-system schedule or off-host backup service was configured. The runbook requires daily scheduling and an off-host/encryption/retention policy to be finalized with deployment.

### Actual local cutover

A pre-migration backup was successfully restored/compared first. The verified existing backend process was stopped. Revision `6a81e4b39c20` was applied, model agreement checked, and the existing **61/100** legacy count imported. Hashes of books/searches/results were unchanged. PostgreSQL `fsync`, `synchronous_commit` and `full_page_writes` were confirmed on. The backend restarted successfully; normal preview routes returned 200. Legacy keys were not cleared and the cap was not raised.

The cutover receipt records 61 retained attempts. Real local data at the checked snapshot comprised **225 books, 74 searches and 404 results**. Subsequent source backups included the single budget row; their recovered copies were blocked while the normal ledger remained 61.

## 4. File changes

| File | Purpose and before/after |
| --- | --- |
| `backend/app/daily_budget.py` | Added durable reservation/status/floor operations; daily use previously depended on Redis alone. |
| `backend/app/models.py` | Added the operational singleton; existing bibliographic tables remain unchanged. |
| `backend/alembic/versions/6a81e4b39c20_add_durable_daily_budget.py` | Added the empty ledger and a no-discard downgrade guard. |
| `backend/app/usage.py` | Kept hourly admission and delegated daily checks/reservations to an explicit durable guard; missing guards fail closed. |
| `backend/app/main.py` | Wired one database-backed daily guard into the existing HTTP transport. |
| `backend/app/llm.py` | Required an explicit client instead of constructing an unmetered default. |
| `backend/app/diagnostics.py` | Added owned budgeted model resources for live tools. |
| `backend/scripts/budget_admin.py` | Added paused-worker import, verified floor, block and rollback-export commands with receipts. |
| `backend/scripts/backup_database.py` | Added private application-schema dumps, snapshot fingerprints, offline restoration, budget quarantine and owned-target cleanup. |
| `backend/scripts/run_isolated_eval.py` | Kept isolated hourly counters but delegated daily use to the same PostgreSQL ledger; reporting now identifies that store. |
| `backend/scripts/check_book_refresh.py` | Updated operational budget reads and fixed a shadowed report variable, retaining the failed capture. |
| `backend/scripts/try_llm.py` | Moved the live model call into the shared budgeted context and guarded module entry. |
| `backend/scripts/try_parse_query.py` | Applied the same shared budget/context and entry guard. |
| `backend/scripts/try_broaden.py` | Applied the same shared budget/context and entry guard. |
| `backend/scripts/try_rank.py` | Used shared budgeted resources alongside its catalog client. |
| `backend/scripts/try_graph.py` | Used the shared budget and explicit safeguard-failure output. |
| `backend/tests/test_durable_budget_tools.py` | Added client requirement and resource-cleanup checks. |
| `backend/tests/test_backup_safety.py` | Added private/exclusive-file, path-boundary and populated-target protection checks. |
| `backend/tests/test_usage.py` | Verified both missing durable protection and hourly Redis outage fail closed. |
| `backend/tests/test_rank.py` | Adapted the existing teaching-tool seam to its owned context without changing the ranking expectations. |
| `backend/integration_tests/test_daily_budget.py` | Added real concurrent/rollover/floor/import/export/outage checks using disposable schemas/key namespaces. |
| `backend/integration_tests/test_cache_usage.py` | Retained SDK retry/cache/isolated-evaluation expectations against durable daily use. |
| `backend/evals/results/budget-cutover-20261109-round17.json` | Retained the actual paused-service import receipt. |
| `backend/evals/results/catalog-refresh-20261109-round17.json` | Retained the failed report-variable capture after otherwise successful book checks. |
| `backend/evals/results/catalog-refresh-20261109-round17-final.json` | Retained the corrected completed actual book/usage check. |
| `backend/evals/results/operations-20261109-round17.json` | Retained aggregate operational evidence, isolated loss results and verified private archive identities without reader data. |
| `backend/evals/results/operations-20261109-round17-final.json` | Added final observed recovery/regression evidence, runtime fingerprints and the unchanged normal budget. The initial receipt's provisional regression label is explicitly pending rather than a completed-test claim. |
| `.gitignore` | Excluded private root backups and dump archives. |
| `docs/operations.md` | Added initialization, cutover, backup, recovery, rollback and deployment scheduling boundaries. |
| `README.md` | Updated onboarding, persistent usage, shared teaching-tool limits and backup instructions. |
| `Lumen_Specifications.md` | Documented the explicitly approved operational table/policy revision while preserving the three core tables. |
| `CLAUDE.md` | Recorded the approved durable-count, privacy and no-reset conventions. |
| `update_version/Lumen_Update_Version_17.md` | Added this round's scope, evidence and submission record. |

No files were deleted and no package/lockfile or frontend implementation changed. The only live schema addition is the approved operational table.

## 5. Project benefits

Redis loss no longer restores spent model allowance. Concurrent API/tool use shares durable accounting, and uncertainty blocks new spending. Backups now have an actual restore/content check rather than only an archive file. The reader's original database is preserved, and recovered budget state cannot be treated as fresh credit by the verified recovery workflow.

## 6. Future impact

- New installations explicitly initialize; upgrades explicitly import with workers paused. Missing initialization deliberately makes uncached AI unavailable.
- Database availability now controls model admission. The 100-attempt setting, hourly limit, public API and model/retrieval behavior are retained.
- The existing backend signature changes, so old parse/result caches become version misses. Raw catalog cache behavior is unchanged; no real usage key was cleared.
- Plain manual restoration outside the documented workflow cannot prove today's remaining allowance. Operators must keep AI stopped and reconcile or block; dropping the ledger is not a supported rollback.
- Backups cover the public application schema and are local/private, not an encrypted off-host or full-cluster recovery solution. Production scheduling, retention and off-host storage remain deployment work.
- The following round can depend on this local checkpoint without an early main merge, as the user requested.

## 7. Verification

| Check | Actual result |
| --- | --- |
| Final native offline suite | **366 passed**, 5.78 seconds. |
| Final native PostgreSQL/Redis suite | **53 passed**, 17.76 seconds. |
| Frontend regression suite | **11 passed**; existing nonfatal Node warning retained. |
| Linux clean locked install/migrations/model agreement | Passed with Python 3.12 and uv 0.12.15; no new upgrade operations after migration. |
| Linux suites before the last backup-only guard test | **365 offline / 53 integration passed**, final recorded replay 1.92 / 8.23 seconds. The final additional guard was verified natively; no claim that this was already a hosted run. |
| Lint/format | Passed for application/script/test scopes; **102 Python files** formatted. The new migration was separately checked. |
| Actual isolated Redis replacement | Passed: six reservations remained six after deleting/replacing only the labeled test Redis and its volume. Four more requests reached the isolated cap of ten; the next was blocked. All provider requests were mocked; production cap stayed 100. |
| Actual cutover | Passed: 61 imported and retained, original book/search hashes unchanged, durable PostgreSQL settings on, preview restarted. |
| Actual private backup/recovery | Passed before and after migration; restored content matched, and recovered daily state was blocked only in the offline copy. |
| Deterministic concurrent-schema regression | Failed before the fix, passed after explicit public-schema selection and guarded empty-target setup. Only the probe's own temporary schema was dropped. |
| Book freshness diagnostic | Initial report failed with a shadowed variable; corrected report completed with both book cases and unchanged PostgreSQL use of **61/100**. Cache reuse is disclosed in that report. |
| Cleanup | Owned Linux containers/volumes/network removed by label checks; isolated diagnostic schemas/keys cleaned. Private archives and sanitized operational evidence retained. |

Local failed lint and checkpoint-synchronization attempts were retained outside the repository before correction/replay. The Redis-loss probe used a fresh disposable schema; no real allowance was reset. The original concurrent-dump failure was reproduced before changing the dump scope; a schema-filtered restore also required safely removing the new target's empty default schema. The report-variable failure was independently identified and its failed JSON was preserved. These failures are not relabeled as successes.

The recommendation prompts, candidate selection and ranking remain unchanged, so no new 20-query quality gate was run for this operational change. No paid model calls, public deployment, UI redesign, production scheduler installation or off-host recovery claim was made. Final file/credential/language review accompanies local checkpoint preparation.

## 8. Approvals and remaining work

The user explicitly approved the PostgreSQL singleton, retaining 100/day, paused verified import, failure blocking and no-reset recovery. That decision was implemented. The later instruction postpones this round's upload/main merge until the next task is finished; this branch remains local for that combined sequence.

Remaining work includes candidate/raw bibliographic storage coverage, deployment packaging/proxy setup, production backup scheduling/off-host policy, UI/documentation polish and public/user acceptance. The backup tooling does not claim those deployment policies are already installed.

## 9. GitHub submission

**Proposed commit title**

`feat: persist daily AI usage and verify private database recovery`

**Proposed commit description**

Redis loss could restore spent AI allowance, and database backups had no verified recovery workflow. Add the approved PostgreSQL current-day singleton, commit atomic reservations before each attempt/retry, fail closed on unknown state and share the same allowance with API workers and provided live tools. Keep hourly IP admission in Redis and the daily cap at 100.

Add explicit paused-worker import/floor/block/rollback commands, a no-discard migration guard, private consistent public-schema dumps and offline content-verified recovery with recovered-budget quarantine. Fix temporary-schema dump races and diagnostic report shadowing, retaining failure evidence. Preserve existing books/search history, public API, prompts and retrieval behavior; no dependencies or providers change.

Validation: 366 offline, 53 native database/cache and 11 frontend tests passed; Linux locked-install/migration/model checks and the preceding 365/53 Linux suites passed. Actual isolated Redis replacement retained usage and blocked excess mocked sends. Real cutover preserved 61/100 and existing data; private backups restored identically, with recovered copies conservatively blocked. No paid-model evaluation, public deployment or installed production backup schedule is claimed.

See `update_version/Lumen_Update_Version_17.md` and `docs/operations.md` for evidence, approved policy, migration/recovery limits and remaining work.

**Actual status:** complete local work prepared for a checkpoint on this branch; not uploaded or merged. The user requested proceeding to the next task first and handling the rounds together afterward. No release or public deployment is authorized.
