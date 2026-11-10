# Budget migration, backups and recovery

The production policy is 100 committed model-attempt reservations per UTC day. The PostgreSQL `ai_daily_usage` table contains one current-day aggregate; it stores no client IP, reader query or request history. Redis continues to enforce the hourly IP policy and hold caches. All provided live model tools share the PostgreSQL allowance.

## Initializing a new installation

Apply `uv run alembic upgrade head` from `backend/`. The new budget table is deliberately empty: new model work remains unavailable until an operator establishes a verified floor.

For a genuinely new installation with no earlier model attempts, while all AI workers/tools are stopped:

```console
uv run python -m scripts.budget_admin initialize --used 0 --confirm-ai-workers-stopped --output ../backups/budget-init.json
```

Use a new receipt filename for every administration action. Never use this zero initialization after losing a ledger or restoring old data. Initialization raises a current-day floor and cannot lower an existing value.

## Migrating an existing Redis allowance

1. Create and verify a backup before changing the schema.
2. Stop every API worker and live model tool using these credentials. The confirmation flag is an operator acknowledgement; it does not discover remote workers.
3. Apply the migration and check agreement with `uv run alembic check`.
4. Import the legacy counter while workers remain stopped:

   ```console
   uv run python -m scripts.budget_admin import-redis --confirm-ai-workers-stopped --output ../backups/budget-import.json
   ```

5. Read the receipt and verify UTC date, cap and stored count. A missing legacy key is unknown usage, so the command conservatively sets the floor to the cap. Negative/invalid counts or disagreeing server dates fail rather than granting an allowance.
6. Start the new backend and confirm health. No legacy/IP/cache key is cleared by the import. Old daily keys can expire normally.

Each outbound attempt reserves against an atomic conditional PostgreSQL update and commits before sending. Concurrent workers cannot exceed the cap. SDK retries reserve again; failures are not refunded. A crash between reservation and send may conservatively overcount. The database clock controls UTC rollover. Missing/future-dated state or a database failure blocks new model work.

## Read-only runtime readiness

The existing `/api/health` endpoint checks PostgreSQL and Redis connectivity. It can correctly report healthy while an installation still lacks a verified daily ledger or model key. Before admitting uncached AI work, use this separate operator check from `backend/`:

```console
uv run python -m scripts.check_runtime_readiness
```

For a running container stack, the same script is included explicitly in the backend image:

```console
docker compose exec -T backend python -m scripts.check_runtime_readiness
```

The command prints a JSON report and returns one of these statuses:

| State | Exit code | Meaning |
| --- | --- | --- |
| `ready` | 0 | The database migration marker matches the packaged heads, Redis responds, the cap is 100, model name/key are nonblank and the known allowance has room. |
| `cached_only` | 2 | Those other local prerequisites pass, but the known current-day allowance is exhausted. Eligible complete cache hits may still work under normal admission/storage rules; no matching cache entry is guaranteed. |
| `not_ready` | 1 | A required local prerequisite is missing, unavailable, inconsistent or unknown; inspect the issue codes and follow the appropriate runbook. |

Each database, Redis and budget component is bounded by a two-second timeout. Database migration/Redis checks run concurrently; the budget is read only after migration markers match. A missing or future-dated budget is unknown, never a zero allowance. An older-day row can produce a logical current-day zero through the existing budget reader without advancing or changing the stored row. A cap other than 100 is reported as a configuration issue; the command does not change it.

The command performs database reads and Redis PING only. It does not migrate, initialize, import, block, reserve, refund, clear keys or create search/IP history. Explicit administration actions above remain separate and still require stopped workers and verified usage evidence. The command suppresses SQL echo and reports safe statuses/error kinds rather than raw validation/driver errors, connection URLs or key values. Its model section reports presence only and always marks remote credentials as unverified. Google Books credentials are optional and do not become a new readiness requirement.

`ready` covers local prerequisites for the configured uncached AI path. It does not establish provider authentication/quota, catalog availability, complete database integrity, recommendation quality, DNS/TLS, production client visibility or backup recovery. The migration check compares the revision marker; use the existing migration/model check and recovery verification for their separate purposes. A missing model key can yield `not_ready` even though a particular cached or legacy keyword request remains usable.

Do not replace the existing container health checks with this command: routine daily exhaustion is an expected operating state, not a reason to classify a live process as unhealthy. Use it as an operator diagnostic after setup/recovery and when investigating maintenance responses. A successful diagnostic does not authorize release or public traffic.

## Private backups and restore verification

From `backend/`, with Docker and the configured local Compose PostgreSQL service available:

```console
uv run python -m scripts.backup_database
```

The command creates a new compressed custom-format dump and private JSON receipt in root `backups/`. It verifies that the configured database and Docker source belong to the same PostgreSQL cluster, exports a read-only repeatable-read snapshot, and fingerprints the public application tables. `pg_dump --schema=public` uses that same snapshot. Unrelated/disposable schemas are deliberately outside this backup scope, preventing concurrent test-schema creation/deletion from breaking an application backup.

The archive is restored to a newly created, labeled container using the same PostgreSQL image, with no network and no published port. Its empty default public schema is checked before removal without `CASCADE`; populated targets are rejected. Every restored public table's count and ordered content hash must match the exported snapshot. Only after this comparison, the recovered ledger is blocked for the current day. The disposable target is then removed with its own anonymous data volume after an ownership-label check. Existing databases are never used as restore targets by this command.

Backups contain the application's stored anonymous reader requests as well as book data. They are compressed, **not encrypted**. Windows directory permissions allow only the current owner and SYSTEM; Unix directories/files use 0700/0600. Backup files are Git-ignored, are never uploaded as project content, and existing files are never overwritten. Failed partial dumps remain private and are not labeled verified. This is a public-schema application backup, not a cluster/role, unrelated-schema, or off-host disaster-recovery solution.

## Recovering from an old archive

Keep all AI workers and diagnostic tools stopped throughout recovery. Restore a trusted archive into a new isolated database and validate its contents before changing service configuration. The verification tool demonstrates this process; it does not automatically replace the normal database.

An old database count is not proof of today's remaining allowance. Before enabling model credentials/traffic, reconcile against verified more-recent operational/provider evidence and raise the usage floor. When that cannot be established, block today:

```console
uv run python -m scripts.budget_admin block-today --confirm-ai-workers-stopped --output ../backups/budget-recovery-block.json
```

The current-day floor becomes at least 100. New model work remains blocked until reconciliation or the natural UTC reset; complete cached work can still follow its normal admission/storage rules. Neither recovery nor a Redis restart is permission to clear counters or raise the cap.

## Rolling application code back

Do not downgrade/drop the daily ledger. The migration's downgrade deliberately refuses to discard accounting state. Older bibliographic application code can coexist with the additional table, but an older migration runner cannot resolve the new revision: use a reviewed rollback startup that retains the current migration files or skips the outdated migration step.

With all AI workers stopped, export a verified floor before starting an older Redis-based worker:

```console
uv run python -m scripts.budget_admin export-redis-floor --confirm-ai-workers-stopped --output ../backups/budget-rollback.json
```

The legacy current-day key receives the greater of its current value and the PostgreSQL floor, with UTC-boundary expiry. If rollback is uncertain, block the PostgreSQL day before exporting. Before returning to the new guard, stop old workers and import the updated Redis floor again. Keep the database ledger and receipts; do not restore an earlier allowance.

## Daily scheduling and remaining deployment choices

Run the verified backup command once daily through the deployment host's approved scheduler, using the same private destination and keeping every receipt. This round supplies and tests the command; it does not install an operating-system schedule or configure a production host. Scheduling, off-host encryption/storage and backup-retention/deletion policy must be finalized with deployment. There is no automatic backup deletion or claim that a local disk backup protects against loss of that disk.
