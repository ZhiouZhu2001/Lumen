# Container startup and controlled proxy

The base Compose file runs the specified five services. Only Caddy publishes host ports; local defaults bind to `127.0.0.1` on HTTP 8080 and HTTPS 8443. The default site is plain HTTP `:80`, so local startup does not request a certificate. This packaging is separate from approval to publish a production site.

## Existing installation and native development

Keep the current project name and `pgdata` volume when changing startup methods. The PostgreSQL image remains `pgvector/pgvector:pg17`; this round does not change the existing database major version or schema. Never use `down -v` on an existing installation. Take a verified private backup before switching an installation.

For Python/Next.js development on the host, publish only the two data services on loopback:

```console
docker compose -f docker-compose.yml -f compose.host.yml up -d --wait postgres redis
```

This retains the existing `.env` database/Redis URLs on ports 5434/6381. `make data` does the same thing. Continue starting the host applications as described in the README. No frontend or Caddy container is needed for this mode. Switching between base and host override can recreate data-service containers to change port bindings; their named database volume is retained. Redis caches and hourly counters may be lost on recreation; the PostgreSQL daily allowance is retained.

## New container installation

1. Copy `.env.example` to a private `.env` and set the database credentials and existing API credentials. Use URL-safe database credential characters, or provide a reviewed encoded connection URL before using reserved URL characters. The backend connection string is assembled from these values as in the previous Compose setup. Neither Docker build receives `.env` or API keys.
2. Check `LUMEN_PROXY_SUBNET` against existing Docker/VPN networks. Its default is `172.30.19.0/28`. The dynamic pool `LUMEN_PROXY_DYNAMIC_RANGE` defaults to `172.30.19.8/29`; `LUMEN_PROXY_IP` defaults to `.2`, inside the subnet but outside that pool. Keeping the fixed address outside dynamic allocation prevents another service taking it during startup. Adjust all three values consistently on overlap. Do not place another container at the proxy address or connect untrusted containers to this project network.
3. Build and start data services, then apply migrations without starting an API worker:

   ```console
   docker compose build backend frontend
   docker compose up -d --wait postgres redis
   docker compose run --rm --no-deps backend alembic upgrade head
   ```

4. Initialize the allowance only if this is a verified new installation with no prior model use. Existing/recovered installations must follow the [budget and recovery runbook](operations.md) instead. Stop all other API workers/live model tools using these credentials. Create a private `backups/` directory using the same permissions as the runbook, and choose a new receipt name. The image includes the existing administration command. One portable way to retain its receipt is to leave the one-off container until copying succeeds:

   ```console
   docker compose run --name lumen-budget-init --no-deps backend python -m scripts.budget_admin initialize --used 0 --confirm-ai-workers-stopped --output /tmp/budget-init.json
   docker cp lumen-budget-init:/tmp/budget-init.json ./backups/budget-init.json
   docker rm lumen-budget-init
   ```

   Check that initialization exited successfully before copying. Choose a new container/receipt name for later actions; never overwrite an earlier receipt. The container has no published port and runs no API worker. Retain the copied receipt privately. `block-today`, `import-redis` and `export-redis-floor` are available through the same one-off entry, with the operational runbook's prerequisites. There is no automatic zero initialization on application startup.
5. Start all services and check the entry point:

   ```console
   docker compose up -d --build --wait
   docker compose ps
   ```

   Open [Spanish](http://127.0.0.1:8080/es), [English](http://127.0.0.1:8080/en) and [API health](http://127.0.0.1:8080/api/health). `make dev` starts the same stack. Health proves dependency connectivity, not allowance initialization or real model/catalog availability; missing budget state still rejects uncached AI work.

6. Run `docker compose exec -T backend python -m scripts.check_runtime_readiness` to inspect local migration, Redis, model-configuration and allowance readiness. It reads only and returns 0 (`ready`), 2 (`cached_only`) or 1 (`not_ready`). The [runtime readiness guide](operations.md#read-only-runtime-readiness) explains each state and its limits. It does not replace initialization, validate remote keys or certify the public deployment.

## Images and routing

The frontend builds locked dependencies with Node 24 in Linux. `NEXT_OUTPUT_STANDALONE=1` enables Next.js output tracing only for the container build; native `npm run build` keeps its existing behavior. The runtime contains the traced server, static assets and public files, and runs as the existing non-root `node` user. This follows the [Next.js standalone output guidance](https://nextjs.org/docs/app/api-reference/config/next-config-js/output). The frontend receives only `BACKEND_URL=http://backend:8000`; model/database credentials belong exclusively to the backend. This backend origin is also baked into Next.js rewrites at build time, so changing the service origin requires rebuilding the image, not just changing runtime environment.

The backend uses the locked Python dependencies and uv 0.12.15. It runs as UID 10001, applies migrations before Uvicorn and disables Uvicorn proxy rewriting/access logs. The budget admin and read-only runtime readiness commands are copied explicitly; tests, reports, transport probes, caches and local environments are excluded from the image. Both Docker contexts allow only relevant inputs. Changing an allowlist is necessary when adding a new top-level build/runtime directory.

The browser sends all traffic to Caddy. `/api` and `/api/*` reach FastAPI directly with their path intact; other paths reach Next.js. Saved-book pages use the private backend URL for server rendering. The native Next.js proxy remains available for native development and retains its 70-second timeout.

Only Caddy has the fixed address in `LUMEN_PROXY_IP`. The container backend trusts that exact address, rather than a whole Docker subnet. Caddy replaces `X-Forwarded-For` with its socket client's address and removes `Forwarded`/`X-Real-IP`. Incoming client identity hints cannot choose an hourly-limit bucket. This setup assumes Caddy is the first ingress: adding a CDN/load balancer requires a separately verified forwarding policy. Docker Desktop may present a host client as its gateway; local tests cannot establish production client visibility. See [Compose networking](https://docs.docker.com/compose/how-tos/networking/).

Caddy's [documented SSE handling](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#streaming) flushes `text/event-stream` immediately. No response buffer, encoder or upstream compression is configured on the API route. The backend's `no-cache, no-transform` and `X-Accel-Buffering: no` headers pass through. The 60-second backend deadline and 15-second real first-book requirement are unchanged. Synthetic delayed frames verify transport, not recommendation quality or that latency gate.

Health checks use the existing API health endpoint, an English frontend page and the Caddy loopback admin API. Caddy's admin listener remains inside its container on loopback and is not published. There is no Caddy access log. Application error diagnostics can still contain request details/stack traces; this is not a complete log-retention policy. Caddy TLS/config state has separate named volumes; keep certificate storage private.

The CI workflow also defines an independent `Container checks` job. It runs `backend/scripts/check_container_stack.py` using the Ubuntu runner's Python standard library and Docker Compose, builds both actual images and starts the real five-service configuration. The job has a 20-minute timeout, needs no project secrets, publishes no image and performs no deployment. A new workflow's local results remain separate from its first hosted run after upload.

The check uses a random project name, an unused diagnostic subnet, Docker-assigned loopback ports and an explicit temporary environment with synthetic database credentials and empty API keys. It verifies actual health, localized pages/assets, missing/invalid book API responses, budget initialization boundaries and the hourly limit under forged forwarding headers. It blocks only its disposable daily ledger, removes only its disposable Redis volume and checks the budget after restart. A test-only ASGI target then verifies exact proxy identity and a 65-second silent SSE interval; its routes and source are not included in either production image. This is transport verification, not a live recommendation-quality or first-book measurement.

The JSON report and bounded failure diagnostics are printed into the job log. The runner also retains its report file under `RUNNER_TEMP` for the job lifetime; no artifact-upload action is configured. Ordinary failures attempt owned-resource cleanup and still fail the job. An ownership mismatch or foreign network attachment refuses destructive cleanup and is reported. Hard termination can prevent cleanup; hosted runner disposal is the final boundary. Locally, inspect the reported project before any manual cleanup. Built images and build cache are retained for local reuse; disposable containers, networks and data volumes are removed.

## Verification, restart and rollback

For disposable tests use a different Compose project name, synthetic credentials, no real API keys, unused loopback ports and a non-overlapping proxy subnet. This creates separate database/Caddy volumes. Confirm ownership through `com.docker.compose.project` labels before removing any test resources; use `down -v` only for that disposable project. Do not run a new zero-initialization command against the normal database to test startup.

Run the same automated check locally with Python 3.12 and a local Docker daemon from the repository root:

```console
python backend/scripts/check_container_stack.py --output backend/evals/results/<new-container-report>.json
```

Choose a new output path each time; existing evidence is never overwritten. The host script uses no project library or private `.env`. Dynamic ports are re-read after restarts. The script checks ownership before removing test resources and never starts or resets the normal Compose project. A test floor of 100 is synthetic guard input, not 100 real model attempts. No public recommendation API calls are requested during the check.

`docker compose restart backend frontend caddy` retains the database. A health check reports readiness; the restart policy handles process exits, not an unhealthy container that is still running. The verified local receipt in `backend/evals/results/container-stack-20261109-round19.json` distinguishes actual application checks from the temporary synthetic transport target. No model call is required for the packaging checks.

For application rollback stop traffic/workers, retain verified private backups, and rebuild the reviewed older application configuration while preserving the current ledger and database. This round introduces no migration. Never downgrade/drop the daily budget or restore an older usage value. Rollback to a pre-round-17 worker follows the export/import/block procedure in the operational runbook. Restore the host-port override when returning to native development.

## Production boundary

No production host, domain, certificate issuance, firewall policy, scheduler or paid service is configured by this round. After separate production approval, the same configuration can select a real site address, public bind address and standard HTTP/HTTPS ports through the `LUMEN_*` variables. Keep data/application services unpublished. Verify DNS, TLS, client IP visibility, streaming, resource capacity and recovery on the actual host before admitting traffic.

The verified backup tool remains a host-side Docker operation; do not mount the Docker socket into either application. Daily scheduling, encryption/off-host storage, retention and the exact host paths remain deployment decisions. Local startup and restore tests do not establish a public disaster-recovery or availability guarantee.
