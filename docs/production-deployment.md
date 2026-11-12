# Production deployment proposal and operator handoff

**Status: prepared for review, not deployed.** No host, domain, paid service, off-host transfer, retention policy or system timer has been purchased, configured or enabled by these templates. Uploading this branch does not authorize those actions or the first public release.

## Recommended approach and decisions

Retain the approved single-VPS, five-service Compose architecture and use Caddy as the first public ingress. Reuse an existing suitable Linux host when available. Otherwise select a provider only after agreeing on region and a monthly budget; this proposal contains no price or availability claim.

An initial capacity-test candidate is an x86-64 Linux host with 2 vCPUs, 4 GiB RAM and 40 GiB SSD. This is an unapproved sizing assumption, not a verified capacity guarantee: measure build peaks, five-service memory/disk use, concurrency and a recovery drill before choosing or paying for a host. Building on the host can require more headroom than steady-state serving. Keep PostgreSQL 17 as used by the actual stack; do not substitute the specification's older image example or migrate an existing database in this deployment step.

Before activation, approve the host/region/budget, owned domain, public-release scope, operator identity, backup execution schedule, encrypted off-host destination, retention/deletion policy and local log limits. A suggested backup target for discussion is one verified daily archive at 03:15 UTC plus up to ten minutes of jitter, with seven daily and four weekly copies. Nothing implements pruning or off-host copying. The proposed daily schedule gives an approximate 24-hour recovery-point target only when jobs succeed; recovery time remains unmeasured.

Alternatives are (1) continue the local-only stack while these choices are unresolved, or (2) use managed data/backup services after separately evaluating their recurring cost and migration implications. The recommended self-hosted approach minimizes stack changes but leaves patching, monitoring and recovery with the operator.

## Reviewed files and identities

- `deploy/production.env.example`: proposed container environment, public Caddy ports and an intentionally invalid placeholder domain. Never launch with the placeholder password/domain or blank model key. Use a unique, high-entropy URL-safe password (letters, digits, `-` and `_`) because the current Compose file embeds it directly in a database URL. An existing password with URI-reserved characters needs a reviewed encoding configuration before startup; do not change an existing database password merely by encoding the environment value. Fill real values only in a private file, not in Git or shell history.
- `compose.backup.yml`: optional **PostgreSQL-only** loopback port. Base Compose still publishes only Caddy; Redis remains private. Do not use the development `compose.host.yml` just to schedule a production backup.
- `deploy/backup.env.example`: separate host-backup settings. It contains no working credential and deliberately gives the backup process no model keys.
- `deploy/lumen-backup.service.example` and `.timer.example`: inactive Linux systemd templates. Review paths, the `lumen` account, the uv executable and Docker permissions before installation. No account is created by these files.

All commands below are a post-approval runbook. Preserve one Compose project name (`lumen`) and `/srv/lumen` checkout throughout setup, backups and recovery. Changing the project name can select different volumes or a different database.

## Prepare and validate without public traffic

1. Install supported Docker Engine/Compose, uv and the locked project Python/dependencies on the selected host. Create the reviewed operator account and private environment/backup directories. Access to the Docker daemon is a powerful host privilege; `NoNewPrivileges` does not make that socket read-only.
2. Check out the approved commit at `/srv/lumen`. Privately prepare `/srv/lumen/.env` from the production example. If host backups are approved, privately prepare `/etc/lumen/backup.env` and percent-encode the actual password in its URL. Keep secrets readable only by the required operator/system service identities.
3. Validate rendered Compose configuration privately. Do not paste it into public logs: it contains resolved secrets.

   ```console
   docker compose --env-file /srv/lumen/.env --project-name lumen -f /srv/lumen/docker-compose.yml -f /srv/lumen/compose.backup.yml config --quiet
   ```

4. Build the approved images before switching traffic. Initially retain loopback-only ingress in the private environment. Start PostgreSQL/Redis, apply the current migrations, and initialize the daily ledger only for a verified genuinely new installation with all AI workers stopped. Follow `docs/operations.md`; an existing/recovered installation never receives an assumed zero floor.
5. Start the remaining services, check connectivity health and run the packaged read-only readiness command. Prove recovery from a synthetic/private test archive before treating backups as operational.

The proposed Caddy mappings are 80/TCP, 443/TCP and the existing 443/UDP mapping for HTTP/3; review the host firewall accordingly. Do not publish backend, frontend or Redis ports directly. If a CDN/load balancer is later introduced, re-review the trusted client-identity chain: current Caddy intentionally uses its socket peer. Keep the existing SSE buffering and timeout configuration.

## Host backup path

The existing verified backup tool runs on the Compose host, requires a localhost database URL, and uses the host Docker CLI. It is not included in the backend runtime image and cannot run there without changing that image's permissions and tooling. Internal `postgres` DNS is for containers, not the native host.

The optional backup override binds `127.0.0.1:${LUMEN_BACKUP_PG_PORT:-5434}` only. Its actual port must match `DATABASE_URL` in the backup environment. Recheck the rendered binding and host reachability after startup; choose another loopback port if it conflicts. This is not an external database endpoint. Docker's distinction between [host ports and container ports](https://docs.docker.com/compose/how-tos/networking/) explains this access path.

The service template fixes the project, Compose files and private Compose environment file explicitly; it does not depend on an interactive shell's directory or exported credentials. It runs from the backend directory, uses the preinstalled environment without synchronization, takes a nonblocking lock, and writes to the private systemd state directory `/var/lib/lumen-backup`. The actual command creates a consistent public-schema dump, verifies it in a disposable offline restore container and blocks only that recovered ledger. Source data and the source allowance are not reset.

Existing archives are compressed but not encrypted. Local disk verification does not protect against loss of that disk. Keep failure receipts/partial archives private and never label them verified. Approve encryption, key custody and the off-host destination before copying real archives. Do not enable automatic deletion before the retention policy and recovery drill are approved.

## Activate the scheduler only after its approval

First run the backup manually using the same service environment and inspect the verification receipt. Verify the service and calendar on the target host. For example, after installing the reviewed templates with mode 0644 at their actual service/timer names under `/etc/systemd/system`:

```console
systemd-analyze verify /etc/systemd/system/lumen-backup.service /etc/systemd/system/lumen-backup.timer
systemd-analyze calendar '*-*-* 03:15:00 UTC'
systemctl daemon-reload
systemctl start lumen-backup.service
systemctl status lumen-backup.service
```

After a successful real-host manual run, and only with schedule approval, enable the timer. `Persistent=true` can trigger a missed job after downtime; jitter shifts its exact start. Observe the [systemd timer semantics](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml) when reviewing this behavior. Inspect `systemctl list-timers` and the private receipts after activation. A timer being active is not proof that a verified archive was produced.

## Public release gate

After explicit release approval, configure the owned domain/DNS and expose Caddy on the approved HTTP/HTTPS ports. Verify the certificate, both locales, book links, real client-IP admission and an uncached bilingual search. Run the full 20-case six-check gate using the shared durable allowance and confirm the real first-book requirement. Synthetic SSE checks do not replace this gate. Read-only readiness verifies local prerequisites, not provider authentication or quota.

Review safe JSON events from `docs/observability.md`, bounded log storage, backup receipts, available disk and the agreed failure-notification process. A concrete local-log proposal is Docker's `json-file` driver with `max-size=10m` and `max-file=3` for each service, subject to retention approval; it is not applied by these templates. No hosted alerting service or automatic notification destination is configured by this proposal.

## Rollback and recovery

Record the previous application commit/images and verified archive receipts before activation. Application rollback must preserve the current migration files and `ai_daily_usage` ledger; do not downgrade or replace the database to roll back logging/UI code. Backend code-signature changes can cause cold caches under the unchanged 100-attempt cap.

To roll back a scheduler change, stop/disable its timer and service, retain all private archives/receipts and restore the previous reviewed units. Do not delete backups as part of rollback. Removing the optional backup override requires reviewing/recreating the PostgreSQL container while keeping the same project and volume; plan the resulting connection interruption. Never use `down --volumes` against production.

For actual disaster recovery, stop all AI workers, restore into an isolated database and verify contents first. Reconcile a trusted current usage floor, or block the current UTC day before resuming workers, as documented in `docs/operations.md`. No old archive proves today's remaining allowance.
