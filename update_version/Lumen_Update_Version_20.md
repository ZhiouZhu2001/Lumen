# Lumen Update Version 20

## 1. Basic information

- **Round:** 20, an implementation round rather than an application release.
- **Date:** 2026-11-10, Europe/Madrid.
- **Branch:** `codex/update-20-container-ci`.
- **Known baseline:** published `main` at `3e28cac0514e4aefe53342b9a43885ca09ce1c38`, containing the completed round-19 five-service packaging and its supplementary regression report.
- **Objective:** replace manual-only container verification with a repeatable local diagnostic and an independent CI job.
- **Actual scope:** a standard-library host runner, a separately mounted synthetic transport target, meaningful failure-boundary tests, the additional workflow job, documentation and retained failed/final receipts. Production application code, image recipes, Compose/Caddy configuration, dependencies, schema, prompts and retrieval logic are unchanged.
- **Working tree:** round 19 was committed, uploaded and fast-forward merged before this branch was created. The new branch started clean; no unrelated user changes were present.

### Round-19 publication receipt

The user explicitly requested merging round 19 into `main` and starting the next round after reviewing its scope and 447 passing tests. The reviewed 15 files were committed as `3e28cac` with the full English description in the commit body. Author and committer were verified as `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`, without co-author or tool attribution.

The branch was uploaded first. [Branch run 42817510966](https://github.com/ZhiouZhu2001/Lumen/actions/runs/42817510966) completed both Backend checks and Frontend checks successfully. The branch was then fast-forward merged and pushed to `main`; [main run 42817902205](https://github.com/ZhiouZhu2001/Lumen/actions/runs/42817902205) also completed both checks successfully. Local `main` and its tracking checkpoint contain that exact functional commit. No pull request, release or production deployment was created.

An initial account-unspecified credential request waited for account selection and was stopped. Explicit noninteractive use of the already saved project-owner account succeeded; credentials were neither printed nor written into project files. The earlier round-19 local/pending status describes its historical checkpoint; this receipt records the subsequent authorized publication.

## 2. Technologies used

No new package, framework, model provider, bibliographic source or service was introduced.

- **GitHub Actions:** a third independent `Container checks` job on the existing Ubuntu 24.04 workflow. It reuses the already pinned checkout action and global read-only permissions, with a 20-minute timeout.
- **Python standard library:** the host runner uses subprocess, temporary files, JSON, IP address calculations and HTTP connections. The CI host does not install the backend dependency tree for this job.
- **Docker Compose:** builds both actual production images, starts the specified services, supplies synthetic environment values, discovers dynamic ports, checks readiness and removes owned test resources.
- **FastAPI/Uvicorn:** an existing-stack synthetic target is mounted only during the final transport phase. It has no model/catalog calls and is excluded from the production backend image.
- **Existing PostgreSQL budget and Redis admission:** tested through actual application endpoints and the existing budget command, against disposable storage and empty API keys.
- **pytest, Ruff and actionlint 1.7.12:** verify failure boundaries, the complete offline backend suite, Python formatting/lint and workflow syntax.

## 3. Implementation

### Independent workflow job

The existing Backend checks and Frontend checks definitions are unchanged. The new Container checks job checks the runner's Python/Docker tools and invokes the host diagnostic. It builds both images rather than assuming a frontend source build proves that a deployable image exists. It performs no registry push or deployment and needs no project secrets.

The job prints its JSON result and bounded failure diagnostics to the normal Actions log. Its report file is stored under `RUNNER_TEMP` during the job. There is no new artifact-upload action or additional token permission. Making this check mandatory for merging remains a separate branch-protection administration choice.

### Owned environment and startup

The runner creates a random `lumen-container-check-<12 hex digits>` project. It finds a non-overlapping diagnostic subnet, keeps the fixed Caddy address outside the dynamic pool and requests Docker-assigned loopback ports. It explicitly overrides all application/Compose variables relevant to this test, uses synthetic database credentials and empty model/catalog keys, and passes an explicit temporary env file instead of the normal `.env`.

Before building, validation rejects additional services, non-Caddy base ports, non-loopback publication, real API keys, changed daily caps, broad proxy trust and frontend secret environment entries. The actual five-service configuration then builds and starts, with all five services required to become healthy. The runner verifies the Caddy configuration, both non-root application users and exclusion of private/test inputs from inspected backend runtime paths.

### Real application checks

The runner checks English/Spanish pages and sampled static assets, API health, and the existing 404/422 distinctions for missing/invalid ISBNs. It submits 20 SSE searches with changing forged identity hints against the uninitialized disposable ledger. All 20 must return the fail-closed 503 response; request 21 must return 429 with Retry-After. The ledger must remain empty rather than being automatically seeded.

Only the disposable ledger is then blocked at its existing cap of 100 through the existing administration command. The runner verifies ownership of the disposable Redis container, removes its container/anonymous data volume and restarts the application chain. An uncached request must still be rejected for the exhausted durable budget. The synthetic floor of 100 is guard input, not 100 real model attempts. No zero initialization, normal-database operation or live evaluation is performed.

Docker can change an ephemeral published port during restart. The runner reads the actual Caddy mapping again after restart and after switching to the probe target. Production fixed port defaults remain unchanged.

### Separate transport target

The test-only `container_probe.py` is read-only mounted into a temporary replacement backend with the existing app package on its import path. Its identity response checks that Caddy's exact peer is trusted, other forwarding hints are absent and three forged input variants produce the same socket-derived effective identity.

Its SSE endpoint sends `status`, stays silent for 65 seconds and then sends `done`. The host reader requires no encoding, the existing no-transform/no-buffering headers, a first frame within two seconds and the complete delayed terminal event. This is a synthetic transport threshold and does not change the real 15-second first-book requirement or 60-second backend deadline. The target is not added to the production API or either image.

### Failure reporting and cleanup

Command timeouts and failed assertions produce a nonzero result, with a new JSON report rather than overwriting previous evidence. Ordinary failures collect a bounded log tail and attempt cleanup. Resource labels and the random-project format are checked before destructive cleanup. A foreign network attachment refuses cleanup rather than removing another project's resource.

Stopped containers are included in ownership checks. Successful cleanup requires no remaining owned containers, networks or volumes. Built images and Docker build cache remain available for local reuse. Hard termination can prevent the cleanup attempt; hosted runner disposal is the final boundary, and local operators must inspect the reported project before manual cleanup.

## 4. File changes

| File | Change and before/after behavior |
| --- | --- |
| `.github/workflows/ci.yml` | Adds Container checks; the two application jobs, permissions and cancellation behavior are unchanged. |
| `backend/scripts/check_container_stack.py` | Adds the standard-library local/CI orchestration, validation, protocol checks, reports and owned cleanup. |
| `backend/scripts/container_probe.py` | Adds the temporary identity/delayed-SSE ASGI target; the existing Docker allowlist excludes it from production. |
| `backend/tests/test_container_checks.py` | Adds ten meaningful cases for cleanup ownership, foreign network attachments, forbidden test configuration and Docker networks with null IPAM configuration. |
| `README.md` | Documents three checks, separate timeouts, local diagnostic scope and the new required-check name. |
| `docs/containers.md` | Adds the repeatable command, test isolation, logging, cleanup and verification limitations. |
| `backend/evals/results/container-ci-20261110-round20-initial.json` | Retains the actual initialization failure before application checks, with the traceback transcription clearly identified. |
| `backend/evals/results/container-ci-20261110-round20-check.json` | Retains the failed restart attempt: earlier checks passed, the old ephemeral port was refused and owned resources were cleaned. |
| `backend/evals/results/container-ci-20261110-round20-final.json` | Records the complete final five-service check, runtime images, exact tested source hashes and delayed-frame timings. |
| `backend/evals/results/container-ci-verification-20261110-round20.json` | Records full offline/JUnit results, workflow validation, preservation/cleanup checks, source hashes and round-19 publication receipts. |
| `update_version/Lumen_Update_Version_20.md` | Adds this implementation and submission record, including actual preceding merge outcomes. |

There are **11 pending files: 3 modified and 8 added**, with no deletions. No production application, dependency lock, migration, Compose/Caddy or frontend source file changed in this round.

## 5. Project benefits

Image construction, startup dependencies and the actual reverse-proxy path can now fail visibly in CI rather than relying on a one-time local receipt. A developer can run the same diagnostic without copying private settings or resetting normal data. The checks guard hourly identity admission and budget initialization/recovery, while the synthetic delayed stream catches proxy buffering or premature termination without model spending. Failure and cleanup evidence is retained instead of weakening checks.

## 6. Future impact

- No API, database or application compatibility change is introduced. Existing image recipes and service defaults remain as reviewed in round 19.
- CI gains image builds and an intentional 65-second silent stream, increasing CI runtime. The new job uses existing CI infrastructure; no new billing plan or paid external service is configured.
- Python 3.12 and a local Docker daemon/Compose are required for the local host runner. The new hosted job uses the Ubuntu runner's Python/Docker installations.
- The new check name can be added to branch protection after separate administration authorization; this round does not change repository protection settings.
- Probe source stays outside production. The backend build allowlist still copies only the existing budget script from the scripts directory.
- Logs/report files are retained in job logs and runner temporary storage, not an uploaded artifact package. A forced kill may prevent local cleanup; images/build cache are intentionally retained.
- Actual production DNS/TLS, real client visibility, capacity, backup scheduling/off-host storage and live recommendation quality remain separate work.

## 7. Verification

| Check actually performed | Result |
| --- | --- |
| Full backend offline suite | **382 passed**, zero failures/errors/skips, pytest console duration 12.22 seconds. This includes the ten new cases. |
| New failure-boundary cases | **10 passed**: three unsafe ownership variants, five forbidden configurations, one foreign attachment and one null network-configuration regression. |
| Ruff lint/format | Passed; **109 Python files** formatted correctly. |
| actionlint | Version **1.7.12**, passed for the final workflow. |
| Workflow structural comparison | Original backend/frontend job definitions, read-only permissions and cancellation configuration match the baseline. |
| Production image builds | Both actual images built in the final diagnostic; frontend production compilation is part of its Docker build. |
| Five-service check | All healthy, non-root users confirmed, actual localized/static/API checks passed. |
| Actual fail-closed admission | Missing budget stayed uninitialized; 20 requests returned 503, request 21 returned 429 despite changing forwarding hints. |
| Redis loss/restart | Disposable floor 100 persisted and continued blocking uncached AI after Redis data loss and application restarts. |
| Synthetic proxy identity | All three forged variants resolved to the same controlled socket-derived identity. |
| Synthetic delayed SSE | First frame **13.93 ms**, terminal frame **65,010.39 ms**, correct status/done sequence and headers. No real book latency is claimed. |
| Resource preservation/cleanup | All three normal Lumen container states/start times unchanged; both failed and final diagnostic containers, networks and volumes removed. |
| Source/evidence agreement | Final diagnostic source hashes and verification-summary hashes match actual files. |
| Preceding authorized upload/main merge | Both round-19 hosted runs linked above passed; remote `main` contains `3e28cac`. |

The first diagnostic encountered Docker's valid `Config: null` for a network. Initialization failed before creating resources and before writing JSON. Its actual traceback was transcribed into the explicitly labeled initial failure receipt; null handling and early-failure reporting were corrected, and the new regression test covers the case. A later run passed startup/admission but reused a stale Docker-assigned port after restart; it failed and cleaned its resources. Re-reading port mappings resolved the issue. The complete final run passed without changing thresholds, application code or the spending cap. Initial lint findings were corrected before final verification.

The host orchestration was executed on Windows against actual Linux Docker images. The exact new job on an Ubuntu GitHub runner has not executed because round 20 is not uploaded. The fresh 382-case suite is offline; no new full 64-case database suite, browser visual sweep or live 20-query recommendation gate is claimed. Round 19's 447-test regression remains separately recorded. No real model/catalog request or normal-data reset occurred.

## 8. Approvals and remaining work

The user authorized the round-19 main merge and continuing the next task. Container CI was the stated next task and implements existing specification requirements within the approved stack. No major architecture, provider, capability, schema, privacy or spending decision was introduced. Round 19 was published and verified before this new scope began.

Round 20 remains local and requires its own upload confirmation. After confirmation, upload the reviewed branch and inspect all three hosted jobs before a separately authorized main merge. Additional branch-protection settings, public deployment, production purchases, backup policy and release remain outside this round.

## 9. GitHub submission

**Proposed commit title**

`ci: verify the five-service container stack`

**Proposed commit description**

The existing CI checks application source but does not build or exercise Lumen's deployable five-service stack. Add an independent Container checks job and a reusable standard-library diagnostic that builds the actual images, checks readiness/localized routing, verifies fail-closed budget and hourly identity admission, and exercises Redis-loss recovery. Use isolated data, synthetic credentials and empty API keys; retain the daily cap at 100.

Mount a separate test-only target for controlled forwarding and a 65-second silent SSE interval, keeping diagnostic routes out of production. Validate ownership before cleanup, refuse foreign attachments, report failures without overwriting evidence and document local/cancellation boundaries. Preserve the two existing CI jobs, permissions, production configuration, APIs, schema, dependency locks and recommendation behavior. No deployment or image publication is added.

Validation: 382 offline backend cases including ten new boundary regressions passed; Ruff lint/format and actionlint 1.7.12 passed. The complete local diagnostic built both Linux images, made all five services healthy, enforced the 20-request hourly boundary and durable budget after Redis loss, and delivered synthetic frames at 13.93 ms and 65,010.39 ms without compression. Three normal Lumen containers were unchanged, and owned failed/final test resources were removed. Retain initial failed receipts and the successful source-hashed report. The Ubuntu-hosted Container checks job and new live recommendation evaluation remain unrun until their respective authorized execution.

See `update_version/Lumen_Update_Version_20.md`, `docs/containers.md` and the round-20 container verification reports. This record also links the successful round-19 branch/main hosted checks and its authorized publication.

**Actual status:** local, uncommitted implementation on `codex/update-20-container-ci`, based on published `main` at `3e28cac`. No round-20 upload confirmation has been received. No round-20 commit, push, pull request, main merge, release or deployment has occurred. Verify the user's author/committer configuration again before any later commit; no co-author or tool attribution is permitted.

### Local dependency checkpoint, 2026-11-10, Europe/Madrid

The user subsequently requested leaving this round unmerged and starting the next round. To keep the scopes reviewable, this completed and verified 11-file round is saved as a local-only commit before creating the dependent round-21 branch. The configured author and committer are reverified as the project owner's identity. No upload confirmation is inferred: this checkpoint is not pushed, `main` remains at `3e28cac`, and round 20's hosted Container checks job remains unrun. The earlier paragraph describes the preceding uncommitted checkpoint; the exact new local baseline is recorded in the next round.
