# Lumen Update Version 30

## 1. Basic information

- **Round:** 30.
- **Date:** 2026-11-15, Europe/Madrid.
- **Branch:** `codex/update-30-docker-workflow`.
- **Baseline:** local round-29 checkpoint
  `ffdf3b8308e75b2093f8d4e0b7a8c8f32bd2a87b`, created from
  `80e5765af602827292f17229bab611d37b9207cf` after checking the twenty-one
  reviewed design files against the retained review manifest. The checkpoint's
  author and committer are `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`. The local
  `main` and last-known `origin/main` remain at `80e5765`; neither round 29 nor
  this round has been uploaded or merged. No remote refresh was required.
- **Objective:** fulfill the request to run the entire current Lumen application
  in Docker, including the redesigned frontend, and remove the native preview
  processes from the normal runtime.
- **Actual repository scope:** four modified files and this new record, five
  files total. The existing five-service Compose architecture, Dockerfiles,
  dependency locks and application behavior remain unchanged. A host backup
  verification readiness race was reproduced and fixed before switching the
  existing installation. The private local HTTP-port setting was changed to
  8081; it is not part of the submission.

The preceding design work was saved as a separate local commit, rather than
mixed into the Docker branch's change scope. Record 29 retains its original
checkpoint-preparation status; this record supplies the actual checkpoint hash.

## 2. Technologies used

No new technology or package dependency was introduced.

- **Docker Desktop and Docker Compose:** build and run the existing Caddy,
  Next.js frontend, FastAPI backend, PostgreSQL and Redis services. Docker health
  checks and `--wait` verify their startup prerequisites.
- **Existing Python 3.12/uv and Node 24 images:** provide the locked backend
  dependencies and the standalone frontend production build. The backend still
  applies existing Alembic migrations before starting Uvicorn.
- **PostgreSQL 17 with pgvector, SQLAlchemy and pg_dump/pg_restore:** create a
  private consistent application backup, verify its restored contents, and
  compare the existing database before and after the runtime transition.
- **Redis 7 and Caddy 2:** retain the existing cache/coordination service and
  the sole browser/API ingress. The application services and data services have
  no published host ports in full Docker mode.
- **pytest and Ruff:** verify the restore readiness fix and existing offline
  backend behavior. Existing container verification checks exercise the real
  images and synthetic transport in a disposable project.
- **Existing Playwright/Chromium installation:** inspect the actual Docker
  website in both locales at desktop and mobile sizes. The Browser plugin was
  not available; no browser package or project dependency was installed.

Host Python was used for operator verification, not as an application server.
The running application does not depend on the previous external preview
launcher or a host Node/Python development server.

## 3. Implementation

### Full Docker workflow and local entry

The documented default is now the root command:

```console
docker compose up -d --build --wait
docker compose ps
```

The existing base Compose configuration builds the current frontend and backend
and runs all five services. `compose.host.yml` is retained for optional native
development; it is not used by the full Docker runtime. Production images do
not automatically reload edited source, so future source changes need another
build/start command. A host Python startup helper is unnecessary.

The local port inventory showed another project's running service on 8080.
Only Lumen's private `.env` received `LUMEN_HTTP_PORT=8081` and an English
explanation. The browser entry is `http://127.0.0.1:8081/es` or `/en`. Caddy
retains loopback bindings, the local `:80` site, and its existing 8443 HTTPS
port mappings; this does not activate public DNS or certificate issuance.
The other project's containers and 8080 listener were left running.

### Existing data handoff

1. Verified the branch, current source, Compose configuration, port ownership,
   database connection identity and non-overlapping proxy subnet. Saved the
   previous design in its separate local checkpoint and created this branch.
2. Built both current application images and ran the isolated container checks
   with synthetic credentials and no real API keys.
3. Identified and stopped only the owned native Next.js/FastAPI preview process
   trees. Verified that their 3000 and 8001 listeners were closed.
4. Recorded the original PostgreSQL cluster identifier, ordered public-table
   content fingerprints, raw daily-usage row and PostgreSQL/Redis volume names.
   Created a private backup and successfully restored it into an owned offline
   disposable container after fixing the readiness race described below.
5. Started PostgreSQL, Redis, backend and frontend using base Compose while
   Caddy was not yet admitting browser traffic. Existing PostgreSQL and Redis
   volumes were reused; no anonymous-volume renewal or volume deletion was
   requested. Compared every recorded database field and volume identity.
6. Started the full stack with `--build --wait`, including Caddy. Checked all
   five health states, read-only runtime readiness, content fingerprints,
   browser behavior, local routing and port isolation. Opened the new Spanish
   entry in the app's browser panel.

All application-table fingerprints matched across the handoff:

| Public table | Rows before and after |
| --- | ---: |
| `ai_daily_usage` | 1 |
| `alembic_version` | 1 |
| `books` | 3759 |
| `search_results` | 1172 |
| `searches` | 195 |

The raw ledger remained `2026-11-15`, **7 attempts**, with the configured daily
cap **100**. No initialization, refund, reset, quota increase or source-data
restore occurred. The PostgreSQL cluster and `lumen_pgdata` mount were identical;
Redis retained the same existing anonymous volume. Readiness reported migration
head `6a81e4b39c20`, healthy Redis, a known available budget and configured model
settings. That read-only report does not validate provider credentials remotely.

### Restore verification readiness fix

The first private dump exported successfully, but its disposable restore check
failed before restoring because the first SQL connection reached a restarting
PostgreSQL server. The original database and containers were not used as restore
targets. The failed archive was retained without a verified receipt.

The image entrypoint first starts a Unix-socket-only bootstrap server and later
restarts PostgreSQL for normal service. The old socket-based `pg_isready` could
report ready during that temporary phase. Three minimal owned offline probes
reproduced one first-query failure during the restart; all three queries after
final TCP readiness succeeded. Database-name and image-compatibility hypotheses
were not supported by the successful final queries.

`verify_archive` now passes `-h 127.0.0.1` to its readiness probe so it waits for
the final server's TCP listener inside the disposable container. The bounded
polling, empty-schema refusal, ownership checks, offline networking, table
fingerprints, recovered-budget blocking and cleanup remain intact. This does
not open a host port or change the original PostgreSQL service's health check.

Two regression tests cover the bootstrap/restart boundary and the timeout path.
The first test failed against the old code before the fix. A retry then produced
a new verified archive and receipt with matching restored table contents,
blocked recovered budget and successful owned-target cleanup. Backups remain
private, Git-ignored, and subject to the existing owner/SYSTEM Windows ACLs.

## 4. File changes

| File | Change and purpose |
| --- | --- |
| `README.md` | Modified. Promote the full Docker command to the normal startup workflow, explain the local port override and rebuild requirement, and retain native development as optional. Previously the full-stack command was mainly a reference alongside native instructions. |
| `docs/containers.md` | Modified. Add the concrete full-stack handoff procedure, local port-conflict handling, safe configuration check, source rebuild behavior, and cluster/table/ledger/volume preservation requirements. |
| `backend/scripts/backup_database.py` | Modified. Wait for the disposable restore server's final TCP listener instead of accepting temporary socket-only bootstrap readiness. |
| `backend/tests/test_backup_safety.py` | Modified. Add a bootstrap restart regression and a readiness-timeout test that verifies no restore SQL is executed and owned cleanup still occurs. |
| `update_version/Lumen_Update_Version_30.md` | Added. Record the separate baseline, actual runtime switch, discovered failure, fix, verification, limits and pending submission status. |

No repository file was deleted. Private `.env`, backups, diagnostic logs,
screenshots and operator scripts are excluded from this five-file scope. No
unrelated prior design file was edited on this branch.

## 5. Project benefits

Normal startup is one repeatable command, and Docker Desktop now shows the
frontend alongside the other four Lumen services. The redesigned frontend and
backend run from reviewed source in their existing production images rather
than separate native preview processes. A single local entry routes pages and
API calls, while direct application and data-service host ports are closed.

The database comparison establishes that the handoff preserved actual books,
search history and spending state. The verified backup supplies a tested private
recovery artifact. The readiness fix removes a reproduced intermittent failure
that could prevent an otherwise valid backup from receiving a verified receipt.

## 6. Future impact and rollback

There is no API, database-schema, data-format, dependency, model-provider,
prompt, retrieval, real-book validation, graph or two-retry policy change.
No new recurring service, scheduler or cost was introduced. The daily cap stays
100, and model/catalog calls were unnecessary for this runtime transition.

Use the new 8081 entry for this installation. Old native URLs on port 3000 no
longer have a listener; newly copied book links derive from the current origin.
The repository default remains 8080 for other installations. Editing source
requires rebuilding the relevant images. Merely restarting an existing
container does not incorporate source changes.

The backup tool remains an operator-side Docker command; it is intentionally
excluded from the backend runtime image. In full Docker mode, future host-side
backups need the existing explicitly local backup connection/override procedure
in `docs/operations.md`; no Docker socket was mounted into the application.

For ordinary shutdown use `docker compose stop`, preserving containers and
volumes. To return to native development if necessary, stop application traffic
and Docker application workers, retain the current database/usage ledger and
verified backup, restore the reviewed host-port override, and use the existing
documented native application commands. Do not delete data volumes, initialize
again or replace today's ledger with an older archive. No rollback was needed
or performed. Public hosting, DNS/TLS, off-host backup retention/encryption and
capacity remain separate deployment decisions.

## 7. Verification

- **Configuration/build:** `docker compose config --quiet` passed. Both current
  production application images built successfully. Running application
  containers' Compose image labels match the build's platform manifests.
  Different Docker image-index/config identifiers were investigated rather than
  treated as source evidence; direct runtime comparison also matched all
  **56** selected backend source/configuration files, all **three** local font
  assets and the original engraving. No runtime probe was added to the images.
- **Offline checks:** Ruff passed and its format check reported **126 files
  already formatted**. The focused backup safety suite passed **5 tests**;
  the complete offline backend suite passed **554 tests** in 36.49 seconds.
  The focused tests are included in that total, not additional test coverage.
  Provider keys were blanked and dummy unavailable database/Redis URLs were used
  for the offline run. A Windows ACL test initially stalled under restricted
  execution; only its owned test processes were stopped, and the successful
  runs used normal Windows access. The stalled run is not counted as a pass.
- **Red regression and real restore:** the new bootstrap test failed against
  the old readiness code with `Query reached the restarting bootstrap server`.
  The three-container diagnostic reproduced the real first-query race once.
  After the fix, archive `lumen-20261115T102832Z-51376b124509.dump` and its
  private receipt passed real offline restore/content verification, recovered
  budget blocking and cleanup. The earlier failed archive remains private and
  unverified. The source database was not modified by backup verification.
- **Isolated five-service check:** the existing verifier passed all **10**
  checks in a separately owned disposable project, including real image builds,
  five healthy services, routing/assets, non-root/runtime exclusions, forged
  identity/hourly limits, missing-budget refusal, durable-budget preservation
  across Redis loss/restarts, synthetic proxy identity and owned cleanup. Its
  synthetic SSE frames arrived at **33.64 ms** and **65030.1 ms**. These are
  transport measurements, not a real first-book latency result. Real model and
  catalog requests: **0**. Disposable resources were removed; built images and
  cache were retained. The backup script change is outside both runtime images
  and the isolated verifier's unchanged application/transport scope.
- **Actual existing installation:** five containers report healthy; the
  read-only runtime check reports `ready`. Cluster identity, all public table
  counts/content hashes, raw usage and both existing data volumes matched the
  pre-handoff snapshot before opening ingress. Only Caddy publishes ports,
  bound to 127.0.0.1 on 8081 and 8443. Native 3000/8001 and former direct
  PostgreSQL/Redis 5434/6381 listeners are closed. The other project's 8080
  listener remains running.
- **Actual Docker browser/API smoke:** Chromium 156.0.8078.4 passed four
  localized home/interaction flows at **1280x900** and **375x812**, plus two
  context-level console/asset checks. Verified route/title, meaningful content,
  no framework overlay or horizontal overflow, local fonts, visible images,
  responsive artwork, language switching and input/filter state. There were no
  console warnings/errors, failed assets or external requests. The initial
  diagnostic expected even hidden images to load and flagged the intentionally
  hidden mobile engraving. Its computed `display:none` and zero bounds were
  inspected; the final check separately asserts that responsive rule, visible
  image loading and a direct successful engraving response. Initial evidence is
  retained; no product code or test result was hidden. `/api/health` returned
  200 with PostgreSQL/Redis `ok`; a deliberately invalid one-character search
  and invalid ISBN each returned 422 before recommendation work. The engraving
  returned 200. No valid search was submitted.

Private logs remain under Git-ignored `backups/round30-*`; the verified archive
and receipt are in `backups/round30-docker-switch/`. Database snapshots,
comparison receipts, runtime content evidence, isolated report, readiness probe,
initial/final browser reports and screenshots are retained in the operator's
private `round30-docker-qa` visualization directory. They are not upload content.

The existing images perform the frontend production build. No frontend source
changed, so the earlier round's 46-test suite and full design matrix were not
rerun as if they were new round-30 results. No full live recommendation gate,
provider authentication request, catalog search, first-book benchmark, hosted
CI run, Safari/Firefox/physical-device test, public TLS or load/release test was
performed. Those checks are unnecessary for the host backup fix and the local
runtime switch, and these results do not certify a public release.

## 8. Approvals and remaining work

The explicit request to move all of Lumen to Docker covers the local switch,
current-code builds and necessary verification. This uses the existing approved
five-service architecture. Port selection and the reversible backup readiness
correction introduce no major technical decision requiring another approval.
No new provider, production host, paid service, public exposure, quota increase
or data migration was activated.

The requested local switch is complete, and all five containers remain running
for review. No reproduced runtime defect remains open in the tested scope.
Future application edits require rebuilding; public deployment and its
environment-specific checks remain separate work. After reviewing the local
handoff, the user explicitly requested merging the current work on GitHub.
The upload scope consists of the separate round-29 design checkpoint (21 files)
and this round's five files, 25 distinct files in total because both rounds
update `README.md`. Both reviewed rounds are included in that request; branch
uploads and the subsequent `main` synchronization will retain the two commits
and wait for successful GitHub checks. No pull request, release or public
deployment was requested.

## 9. GitHub submission

**Proposed commit title:** `fix: make Docker handoff and restore readiness reliable`

**Proposed commit description:**

Make the full existing five-service Docker stack the documented normal local
workflow, with a single build/start command, a private alternative HTTP port,
clear source-rebuild behavior and a data/usage-preserving handoff. Keep native
development optional and remove any dependency on a temporary host launcher
from normal operation. Run the current approved frontend and backend images
behind the sole local Caddy entry.

Fix the backup verifier's reproduced startup race by waiting for the disposable
PostgreSQL server's final TCP listener rather than its temporary socket-only
bootstrap server. Add regression coverage for the restart boundary and a
timeout that must not execute restore SQL. Preserve private archives, ownership
checks, offline restoration, content fingerprints and recovered-budget blocking.

Verification: 554 offline backend tests, Ruff and formatting passed; the new
regression failed before the fix, and the five-test backup suite passed after
it. A real private dump/restore verified every public table. The isolated
five-service verifier passed ten checks including synthetic 65-second streaming
without provider calls. The actual installation's five services are healthy,
its full table fingerprints/cluster/volumes and 7/100 usage were preserved, and
desktop/mobile bilingual browser and API smoke checks passed. No real model or
catalog search was needed; public deployment and live recommendation acceptance
were not performed.

Keep APIs, schema, dependency locks, graph/retrieval/provider behavior and the
100-call policy unchanged. The local port override, backups and diagnostic
evidence are private and excluded. This five-file round depends on the separate
round-29 checkpoint `ffdf3b8`; the user's request to merge the current work on
GitHub includes both reviewed rounds. See
`update_version/Lumen_Update_Version_30.md` for implementation,
file scope, evidence, compatibility, rollback and remaining deployment work.

**Status at upload preparation (2026-11-15):** the user requested merging the
reviewed current project on GitHub after the local completion report. Round 29
retains checkpoint `ffdf3b8` on `codex/update-29-editorial-redesign`; these five
round-30 files are being prepared as a separate commit on
`codex/update-30-docker-workflow`. Both branches will be uploaded under that
request. The `main` fast-forward remains pending successful hosted checks and
a final remote-head comparison. No pull request, release or public deployment
has occurred. The completion reply and private submission receipt will identify
the actual resulting commit and remote check/merge status without rewriting
the historical round-29 record.
