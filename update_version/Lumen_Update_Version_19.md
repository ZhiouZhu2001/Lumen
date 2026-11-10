# Lumen Update Version 19

## 1. Basic information

- **Round:** 19, an implementation round rather than an application release.
- **Date:** 2026-11-09, Europe/Madrid.
- **Branch:** `codex/update-19-container-stack`.
- **Known baseline:** `e5ce8dd668a33435b2f4695bffd26e3099db79a0` on local `main`, matching its recorded `origin/main` tracking checkpoint. Rounds 17 and 18 had already been uploaded and merged in the preceding chat. No remote synchronization or upload is claimed for this round.
- **Objective:** complete the specified five-service container startup and controlled local reverse-proxy path.
- **Actual scope:** frontend image/output tracing, bounded build contexts, backend container entry and budget-administration availability, five-service Compose networking/readiness, Caddy routing, an optional native-development port override, documentation and sanitized local verification evidence.
- **Working tree:** clean before branch creation. All changes listed below belong to this round; no existing user changes were overwritten. No production environment was modified.

## 2. Technologies used

The work uses the already specified Docker Compose, Caddy, Next.js, Node.js, Python, FastAPI, PostgreSQL and Redis stack. No package dependency, model provider, bibliographic source or database migration was added.

- **Docker multi-stage builds:** install the locked frontend dependencies and compile with Node 24 on Linux; copy only the standalone runtime, public files and static assets to the runtime image.
- **Next.js output tracing:** enable `output: standalone` through a container-build flag. Native builds retain their prior output behavior, including avoiding an additional Windows standalone-symlink requirement.
- **Docker build-context allowlists:** keep local environments, secrets, caches, tests and evaluation archives out of application images.
- **Caddy 2:** serve as the sole published entry, route intact API paths to FastAPI and other paths to Next.js, and preserve streaming headers without API compression/buffering. The implementation uses its documented automatic immediate flush for `text/event-stream`.
- **Compose networking/IPAM and health dependencies:** assign Caddy one exact trusted peer address outside the dynamic pool. Readiness checks gate startup on the data services and applications.
- **Existing budget tools and PostgreSQL singleton:** make the established administration command available in the backend image without automatic allowance initialization.
- **httpx and temporary Python orchestration:** drive actual isolated application requests, recorded-fixture cache/storage setup, spoofed-header admission checks and a separately labeled delayed transport target. These checks use no live model or catalog requests.

## 3. Implementation

### Complete container startup

Previously Compose started only PostgreSQL, Redis and the backend. The frontend had no Dockerfile, and the repository had no Caddy configuration. The base file now starts all five specified services, with restart policies and health checks. Only Caddy publishes ports, on loopback by default. The default plain-HTTP site does not request certificates. Separate named Caddy data/config volumes prepare certificate-state persistence without issuing a production certificate.

The existing PostgreSQL image and `pgdata` volume identity remain unchanged. Data ports move to `compose.host.yml`, which publishes PostgreSQL 5434 and Redis 6381 only on loopback for the existing native development workflow. `make data` starts this mode; `make dev` builds and waits for the complete container stack. Existing users must select the documented mode when switching configurations. No normal service was recreated during verification.

### Application images

The frontend uses `npm ci`, the current lockfile and a Linux production build. Its runtime runs as the existing `node` user and includes static/public assets that standalone tracing does not automatically copy. It receives only its private backend origin. That origin is set consistently for build-time rewrites and runtime server-rendered details; changing the service origin requires a rebuild.

The backend retains locked production dependencies, aligns the uv image with the existing CI version 0.12.15, includes only the existing budget administration script, and runs as UID 10001. Alembic still runs before Uvicorn. The entry keeps `--no-proxy-headers` and adds `--no-access-log` so standard request access lines do not persist peer addresses. This is not a complete error-log retention policy.

Both build contexts allow only explicit inputs. Neither build consumes `.env` or model/catalog keys. Compose passes an explicit backend environment rather than forwarding the entire secret file. The frontend receives no database or model credentials. A new top-level build/runtime directory will require a corresponding allowlist update.

### Controlled forwarding and streaming

Caddy routes both `/api` and `/api/*` directly to the backend, preserving the path and bypassing the native Next.js rewrite. Other paths reach the frontend. Saved-book server rendering uses the private backend service origin.

The backend trusts only `LUMEN_PROXY_IP`. Its default static address `.2` is excluded from the edge network's dynamic `.8/29` pool, preventing startup order from allocating it to another service. Subnet, dynamic range and fixed address can be changed together for Docker/VPN conflicts. Caddy replaces client-supplied `X-Forwarded-For` with its socket client and removes `Forwarded`/`X-Real-IP`. This assumes Caddy is the first ingress; a future CDN/load balancer needs its own reviewed policy.

The API route enables neither encoding nor response buffering, disables upstream compression negotiation, and preserves the backend's SSE/no-transform headers. Caddy flushes SSE immediately. The native Next.js proxy retains its 70-second timeout; the backend's 60-second deadline and real first-book requirement remain unchanged.

### Initialization, restart and rollback boundaries

Health checks do not initialize the daily budget or establish model availability. Missing state rejects uncached AI work. The existing explicit admin tool is usable through a one-off container; the guide retains the receipt before removing that container. Repeated initialization cannot lower a current-day floor. Existing imports/recovery still require the operational runbook and stopped workers.

Redis recreation may retain its anonymous volume; an actual loss of that disposable data was separately tested. The PostgreSQL ledger and saved books survive either path. Code rollback introduces no round-19 migration, but must retain the current budget table and follow the existing old-worker export/import policy. The host-side backup tool does not require exposing the Docker socket to applications.

## 4. File changes

| File | Change and before/after behavior |
| --- | --- |
| `frontend/Dockerfile` | Added locked build and non-root standalone runtime stages; previously no frontend image existed. |
| `frontend/.dockerignore` | Added explicit build-input allowlist; local secrets/output/dependencies are excluded. |
| `frontend/next.config.ts` | Enables standalone output for container builds only; native builds and existing API timeout/routing remain available. |
| `backend/Dockerfile` | Pins uv to the existing CI version, copies the admin command, adds a non-root runtime and suppresses request access logs. |
| `backend/.dockerignore` | Replaces the short denylist with a runtime-input allowlist; excludes tests, reports, environments and bytecode. |
| `docker-compose.yml` | Expands three services to five, limits published ports to Caddy, explicitly passes backend settings, supplies exact proxy trust, separate static/dynamic address allocation, health checks and restart policies. |
| `compose.host.yml` | Added optional loopback-only PostgreSQL/Redis ports for native application development. |
| `Caddyfile` | Added intact API routing, frontend fallback, controlled forwarding and uncompressed/unbuffered SSE transport. |
| `.env.example` | Documents host-mode ports and local Caddy/network defaults; contains no real credentials. |
| `Makefile` | `dev` waits for the complete stack; adds `data` for native development and expands application logs. |
| `README.md` | Links the complete startup guide, updates the native data command and describes the implemented local proxy and remaining production boundary. |
| `docs/containers.md` | Added setup, private initialization receipts, forwarding assumptions, verification, restart/rollback and production limitations. |
| `backend/evals/results/container-stack-20261109-round19.json` | Added sanitized local verification receipt, runtime image IDs, configuration/source hashes, corrections and explicit test limitations. |
| `backend/evals/results/regression-20261110-round19.json` | Added the later full-regression receipt, source/archive/log hashes, JUnit totals, isolation/cleanup results and explicit live-evaluation boundaries. |
| `update_version/Lumen_Update_Version_19.md` | Added this implementation, verification and submission record. |

No project files were deleted. Application logic, prompts, retrieval parameters, package locks, evaluation thresholds and database schema were not changed.

## 5. Project benefits

A clean installation can build and start the whole specified service chain through one entry. Native development retains a documented data-service mode. Exact proxy trust prevents a browser-supplied identity hint from selecting another hourly counter. Image contexts and per-service environments limit accidental secret inclusion. Startup checks expose missing services early, and explicit initialization preserves the existing spending safeguard.

## 6. Future impact

- **Actual compatibility change:** base Compose no longer publishes data/backend ports; host development uses the new override. Existing named database data is retained, but switching port bindings can recreate containers. Redis cache/hourly state may be lost; this cannot reset the PostgreSQL daily ledger.
- **Actual image behavior:** frontend builds produce Linux standalone output, both application runtimes are non-root, and backend access logs are disabled. New runtime/build directories need explicit inclusion. Native frontend build behavior remains unchanged.
- **Actual APIs/data:** public request/response formats, database schema, provider settings and daily 100-attempt policy are unchanged. No migration or destructive operation targets the real data.
- **Actual operations:** health checks establish local readiness, not AI initialization, live-source quality or process capacity. Restart policies act on exits; they do not restart a still-running unhealthy process.
- **Possible later work:** public DNS/TLS/ingress verification, capacity checks, backup scheduling/encryption/off-host storage/retention and release approval remain separate. The current hosted CI does not build Docker images or run this local transport probe.

## 7. Verification

The disposable project used its own PostgreSQL/Redis storage, synthetic database credentials, empty model/catalog keys, unused loopback ports and a dedicated network. No full live recommendation gate or production action was performed.

| Check actually performed | Result |
| --- | --- |
| Linux backend and frontend Docker builds | Both exited zero. Frontend production compilation and TypeScript checks passed. |
| Five-service startup/readiness | All five services healthy after correcting fixed/dynamic allocation. |
| Compose port/environment checks | Only Caddy publishes base ports, all on loopback; the optional host data ports are loopback-only; frontend receives no backend secrets. |
| Caddy validation and image checks | Configuration validated; backend UID 10001 and frontend UID 1000 confirmed; environment/test artifacts absent from inspected runtime paths. |
| Actual HTTP pages and assets | English/Spanish pages and sampled JS/CSS returned 200; health returned 200; missing/invalid book APIs retained 404/422. |
| Uninitialized budget | An uncached SSE request returned 503 without a model send. |
| Explicit container administration | Set a synthetic floor of 100 in the disposable database; subsequent initialization at zero retained 100. Named-container receipt copying succeeded and matched its output. This floor is not a claim of 100 actual model calls. |
| Actual application cache stream | A recorded Spanish fixture with clearly synthetic completed-search input streamed two book events and `done` through Caddy despite the exhausted test allowance; no compression, no-transform and no-buffering headers verified. |
| Actual saved-book paths | Public detail JSON and server-rendered English/Spanish saved pages succeeded using private backend routing; original provider evidence remained excluded from public JSON. |
| Actual hourly admission | Twenty requests were admitted, including the initial missing-budget request; request 21 returned 429 with Retry-After despite changing forged identity headers. One expiring Redis IP key was observed. |
| Redis data loss and application restart | After removing only the owned disposable Redis container/anonymous volume, its IP keys were gone; saved books and the PostgreSQL floor of 100 survived. Uncached AI remained blocked. Applications restarted and health recovered. |
| Separate synthetic identity echo | Three malformed/different forwarding hints produced the same effective socket identity; the peer matched the exact trusted Caddy address and other hints were removed. No diagnostic route was added to the real app. |
| Separate synthetic delayed SSE | First `status` at **14.27 ms**, terminal `done` at **65,010.20 ms**, after 65 seconds of silence, without response compression. This measures transport, not a real book or recommendation latency. |
| Diagnostic restoration | Restored the real backend, confirmed health and 404 for both temporary diagnostic paths before cleanup. |
| Native frontend regressions | **11 passed**; ESLint passed. Existing nonfatal MODULE_TYPELESS_PACKAGE_JSON warnings were retained. |
| Original installation preservation | Existing PostgreSQL/Redis container IDs remained unchanged. Public content fingerprints/counts remained **225 books, 74 searches, 404 results**; real daily use stayed **61/100**. |
| Cleanup | Ownership labels checked; disposable project containers, networks and named volumes removed. Original services remained running. |

The first startup failed because dynamic allocation occupied the intended fixed proxy address; the final separate dynamic range resolved this, and the full stack passed. The first Redis loss assertion incorrectly assumed Compose force-recreation would discard its anonymous volume; the corrected check explicitly removed only that disposable volume. The separate temporary transport app initially lacked `/app` on its import path when started from `/probe`; its test-only environment was corrected. Production application startup was unaffected by that diagnostic import error. Initial logs and temporary check code remain in the ignored local check directory, and the sanitized receipt records these corrections; failures were not relabeled as passes.

No new backend unit/integration suite, browser visual sweep or live 20-query quality gate was run: backend application logic, UI markup, prompts and retrieval are unchanged. Actual container/API/storage/admission checks target this configuration change. No paid AI or live catalog call was made. Hosted CI for this round awaits a separately confirmed upload; earlier rounds' hosted results are not substituted for it.

Final text checks removed preexisting trailing spaces from two Makefile target labels. Recipe commands and the tested container configuration were unchanged; the receipt's Makefile hash was refreshed. The final 14-file scope, source hashes, English/attribution policy, credentials exclusion and Git whitespace checks were then verified.

### Supplementary full regression, 2026-11-10, Europe/Madrid

After reviewing this round's details, the user requested running tests first. This is further verification of round 19 on the same branch, not a new implementation round. The preceding omitted-check statement describes the original checkpoint; the following full regression was actually executed afterward. No application, dependency, schema, proxy or build configuration was changed for this continuation.

A new source archive captured **211 current backend/frontend files**, excluding local environments and ignored private data. Independent Linux jobs used temporary PostgreSQL 17 and Redis 7 containers, synthetic test credentials, empty model/catalog keys and no connection to the normal database/cache. The backend test job used the verified round-19 backend image with development tools installed only into its disposable container; the production image and its non-root entry were unchanged. The frontend job used Node 24 with a clean locked installation and no existing build cache.

| Supplementary check | Actual result |
| --- | --- |
| Full offline backend suite | **372 passed**, no failures, errors or skips; pytest reported 3.04 seconds. |
| Full PostgreSQL/Redis integration suite | **64 passed**, no failures, errors or skips; pytest reported 10.30 seconds. Includes all 20 historical cases persisted with real foreign keys; this is replay, not fresh live recommendation evaluation. |
| Frontend native regression suite | **11 passed**, zero failures; includes details, error distinctions and SSE parsing. |
| Total executed test cases | **447 passed**. The historical cases are already included in the integration total, not counted again. |
| Backend lint/format | Ruff passed; all **106 Python files** formatted correctly. |
| Fresh database migrations | Both existing migrations applied to a new temporary database. |
| Migration/model comparison | Passed: no new upgrade operations detected. |
| Frontend ESLint | Passed. |
| Clean Linux frontend production build | Passed, including TypeScript checks. |
| Earlier container receipt | Its **12 recorded source hashes** still match. The five-service/65-second transport probe was not rerun in this supplementary check. |
| Isolation and test cleanup | No leftover disposable schemas or Redis keys; the temporary public budget remained uninitialized. All test containers, their anonymous volumes and the owned network were removed after label checks. |
| Existing Lumen services | All **3** preexisting Lumen container states and start times were unchanged; normal services were neither started nor reset. No current-day real usage value was inferred from the earlier 61/100 receipt. |

Both Linux jobs exited zero. JUnit reports, complete logs and the source archive remain in the ignored local check directory; their hashes and sanitized totals are retained in `backend/evals/results/regression-20261110-round19.json`. The JUnit durations in that receipt are XML-reported suite times and differ slightly from pytest's rounded console totals above. The receipt records both the source snapshot and exact job images. Existing nonfatal Node module-type and cold build-cache messages were retained.

An initial receipt-preparation assertion compared every container on the shared machine and detected an unrelated worker that was already restarting before the checks. The observation is retained without publishing the other project's identity. Lumen's own container states were checked separately and remained unchanged. No application or test assertion was altered, and all 447 test cases had already passed before this receipt check.

This supplementary verification introduces one additional report, bringing the round's pending scope to **15 files**. No real model/catalog request, fresh live 20-query gate, browser visual sweep, GitHub upload or hosted run was performed. Earlier container transport evidence remains distinct from these newly executed full suites.

## 8. Approvals and remaining work

The user requested continuing the project in this chat. The preceding completed round identified deployment packaging/proxy work as the next step. This implementation follows the existing specified stack and adds reversible local configuration; no new major architecture, capability, provider, schema, privacy or spending decision was required. The previously approved durable 100-attempt policy is retained.

No public release, deployment, domain purchase, paid service, host scheduler or off-host retention policy is approved or performed here. Remaining work includes those concrete deployment choices and actual-host verification, later UI/README media polish and user acceptance. Adding hosted container checks is also a future improvement; this receipt is local evidence.

## 9. GitHub submission

**Proposed commit title**

`build: complete the five-service container stack`

**Proposed commit description**

Lumen's Compose configuration omitted the frontend and Caddy, leaving the full specified startup and controlled ingress path incomplete. Add a locked standalone frontend image, restricted build contexts and non-root application runtimes. Start all five services with health dependencies, restart policies and loopback Caddy defaults. Route intact API paths directly to FastAPI and replace incoming identity hints while trusting only Caddy's fixed address outside the dynamic pool.

Preserve the existing database image, named volume, public APIs, retrieval behavior and 100-attempt allowance. Keep explicit budget initialization through the existing container administration command. Move native data ports to an optional loopback override, document that compatibility change and provide initialization, rollback and production boundaries. Public deployment, paid services and backup scheduling/storage remain separate decisions.

Validation: both Linux images built successfully, all five services became healthy, and actual bilingual/static/detail/cache-stream requests passed. Missing/exhausted test budget state blocked uncached model work; forged forwarding headers could not evade the 20-per-hour limit. Redis data loss and application restart retained saved books and the durable ledger. A separate synthetic 65-second stream delivered its first frame at 14.27 ms and its terminal frame at 65,010.20 ms without compression. Eleven frontend regressions and ESLint passed. Real public-table fingerprints and the 61/100 allowance were unchanged; disposable resources were removed. No new live recommendation gate, hosted container run or public deployment is claimed.

See `update_version/Lumen_Update_Version_19.md`, `docs/containers.md` and the sanitized container verification receipt.

Supplementary validation on 2026-11-10: a clean Linux run passed 372 backend unit tests, 64 PostgreSQL/Redis integration tests and 11 frontend tests, 447 in total. Ruff lint/format, fresh migrations, migration/model agreement, ESLint and the frontend production/TypeScript build passed. The 20 historical persistence cases are included in the integration suite. The earlier container receipt's source hashes match; its five-service transport probe was not repeated. Existing Lumen container states were unchanged, and owned test resources were removed. See `backend/evals/results/regression-20261110-round19.json`; no fresh live AI evaluation or hosted verification is claimed.

**Actual status:** local uncommitted implementation on `codex/update-19-container-stack`. No round-19 upload confirmation has been received; no commit, push, pull request, main merge, release or deployment has been performed. Commit identity verification remains required before any later commit. Upload confirmation applies only to this reviewed branch and scope; merging or deployment requires its own authorization.

### Submission authorization, 2026-11-10, Europe/Madrid

After the detailed scope review and supplementary 447-test regression, the user explicitly requested merging this branch into `main` and starting the next implementation round. This authorizes the necessary round-19 commit, branch upload and main merge for the reviewed 15-file scope. No pull request, release or production deployment is included. The earlier local-only paragraph records the preceding checkpoint.

Before preparing the functional commit, the remote `main` was fetched and still matched the recorded `e5ce8dd` baseline. The configured author and committer were verified as `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`. The local source/verification hashes, English content, credentials exclusion, attribution and whitespace checks are rechecked before staging. Branch upload, hosted checks and the main merge will be recorded after their actual outcomes are known.
