# Lumen Update Version 16

## 1. Basic information

- **Round:** 16, an implementation round rather than an application release.
- **Date:** 2026-11-09 (Europe/Madrid).
- **Branch:** `codex/update-16-continuous-integration`.
- **Baseline:** `85bbf3346f7a58df9009a9046520ad997cb31b6a`, independently verified on remote `main` and `codex/update-15-catalog-refresh` after the authorized upload and fast-forward merge.
- **Objective:** implement the specification's automatic GitHub checks for code quality, tests, migrations and the production frontend build.
- **Actual scope:** one GitHub Actions workflow, README usage/boundary documentation and this record. Runtime application code, dependencies, lockfiles and deployment configuration are unchanged.

The user explicitly requested merging Update 15 into main and continuing with the next task. Update 15 was committed as `feat: refresh stale saved-book metadata by exact ISBN`, pushed with the reviewed English description and fast-forward merged. Author and committer were the verified project owner, `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`. Both remote refs matched the full baseline above. No additional author credits, collaborators, pull request, release or production deployment were added. Update 15's earlier local-review status is superseded by this publication record.

The tree was clean before this new branch was created. No unrelated user edits were included. The previously highest update number was 15; existing records remain intact.

## 2. Technologies used

No new application framework, runtime dependency, model provider, database schema or paid service was introduced.

- **GitHub Actions YAML:** define push, pull-request and manual triggers, two independent Ubuntu 24.04 jobs, a 15-minute timeout per job, read-only contents permission and cancellation of superseded runs. The [official workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax) was checked before implementation.
- **Official checkout and runtime actions:** pin checkout, setup-uv and setup-node to full verified commits. Tag-to-commit mappings and declared inputs were read from the official repositories. These are CI tools, not additional project authors or collaborators.
- **Existing uv/Python tooling:** use uv 0.12.15, the tracked Python version file and `uv sync --locked --dev`. Following the [official uv integration guidance](https://docs.astral.sh/uv/guides/integration/github/), dependency installation and command execution use the existing lockfile.
- **Existing Node/npm/Next.js tooling:** use Node 24, `npm ci`, lint, native tests and the production build's TypeScript checks. No package manifest or lockfile was changed.
- **PostgreSQL 17 and Redis 7 service containers:** supply fresh temporary test services. PostgreSQL's major version matches the repository's existing development deployment; no vector extension is needed by the current schema. [GitHub service-container guidance](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers) informed health checks and runner networking.
- **actionlint 1.7.12:** validate workflow syntax, expressions and action inputs with a temporary official release binary whose published SHA-256 checksum was checked.
- **Docker-based local verification:** execute the same run commands against a clean source copy with freshly installed dependencies and isolated service containers. This exercises Linux behavior without changing local application services or mounting project secrets.

## 3. Implementation

### Triggers and boundaries

The `CI` workflow is configured for pushes on all branches, normal pull-request events and manual dispatch. Manual dispatch requires the workflow to be present on the default branch. Every job checks out the relevant repository revision using normal event semantics. Checkout credentials are not persisted. The workflow-level token grants only `contents: read`; project secrets are not referenced.

Two jobs run independently, so a frontend failure does not conceal the backend result or vice versa. Each has a 15-minute timeout. A concurrency group based on workflow and pull-request number or Git ref cancels superseded in-progress runs. No path filter skips a check because a change touches only a shared/root file.

The workflow publishes checks; it does not itself configure required branch checks, automatic merging or deployment. Protecting main with required check names is a separate repository setting and has not been changed in this round. Workflow creation does not grant authorization for future uploads, main merges, releases or deployment.

### Backend checks

1. Check out source and install the pinned uv version with dependency caching keyed by `uv.lock`.
2. Install the Python selected by `backend/.python-version` and synchronize locked development dependencies. A stale lockfile causes installation failure rather than silent resolution updates.
3. Check Ruff lint and formatting over application code, scripts, tests, evaluations and integration tests.
4. Apply `alembic upgrade head` to the new temporary PostgreSQL database and run `alembic check` to detect migration/model disagreement.
5. Run the existing offline unit suite, then the explicit native PostgreSQL/Redis integration suite. Existing uniquely named test schemas/key namespaces retain their own cleanup behavior.

Both service containers have health checks before use. Runner connections target the job's mapped localhost ports. The `ci_only` password is deliberately public disposable test configuration, not a project credential. Empty model/catalog keys and isolated URLs keep the workflow independent of local `.env` files and production services. The daily setting remains 100. No live evaluator, real catalog diagnostic or provider/model invocation command is included.

Commands run in the backend directory. After the locked sync, `uv run --no-sync` executes the checks without performing an additional implicit dependency synchronization.

### Frontend checks

Check out source, install Node 24 with npm's download cache keyed by `frontend/package-lock.json`, install using `npm ci`, run ESLint and native tests, then run the production Next.js build. The build includes TypeScript checking and verifies both localized home/detail routes. Next.js telemetry is disabled for the CI process. A backend server or AI credentials are not required to prerender the existing route shells.

### Pinned external actions

| Action | Verified ref | Fixed commit |
| --- | --- | --- |
| `actions/checkout` | `v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `astral-sh/setup-uv` | `v9.0.0` | `c771a70e6277c0a99b617c7a806ffedaca235ff9` |
| `actions/setup-node` | `v7` at verification | `949feb2413d6458794dcd2491c4babbbce0c15c1` |

Future action/runtime upgrades require deliberate review; moving tags cannot silently change these pinned action implementations. Service images retain explicit major-version tags and are not claimed to have immutable digests in the workflow.

## 4. File changes

| File | Change | Before and after |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Added CI triggers, permissions/concurrency, ephemeral services and backend/frontend checks. | No GitHub workflow existed; uploaded revisions can now receive reproducible pass/fail checks without project secrets. |
| `README.md` | Added CI behavior, requirements, reproduction guidance and branch-protection/hosted-run boundaries. | Verification was documented only as local commands; readers can now understand the automated checks and what remains manual. |
| `update_version/Lumen_Update_Version_16.md` | Added this record with actual local Linux evidence and submission status. | This round had no implementation/verification record; its exact scope and limits are now reviewable. |

No files were deleted. No application code, API, frontend presentation, package, lockfile, migration, runtime setting, spending limit or database record changed.

## 5. Project benefits

- Repeats the existing verification on clean environments instead of depending on an author's installed dependencies or `.env`.
- Gives backend and frontend failures separate, readable checks.
- Exercises real database/cache behavior as well as offline logic and frontend compilation.
- Checks that a fresh database can migrate and that migrations still describe the models.
- Avoids consuming the user's AI allowance or sharing project credentials with pull-request jobs.
- Reduces redundant runner work by canceling superseded runs and caching dependency downloads.

## 6. Future impact

- **Runtime compatibility:** application source and all dependency locks are unchanged. Existing search cache signatures, API contracts, database schema and local services retain their current behavior.
- **Repository workflow:** after upload, ordinary pushes and pull requests can trigger `Backend checks` and `Frontend checks`. Enforcing them as merge requirements still needs a separate branch-protection decision/configuration.
- **Costs and credentials:** the repository was verified public. No new paid service, billing setting, production credential or deployment resource was configured. Runner usage remains subject to GitHub's existing account/repository policies. No AI requests are part of these checks.
- **Reproducibility:** Python follows the tracked version file, Node remains on major 24, uv is fixed at 0.12.15 and project dependencies follow their lockfiles. Setup/download infrastructure and service-image patches still depend on upstream availability.
- **Live quality:** CI does not replace the mandatory 20-query six-check gate for future prompt or recommendation-retrieval changes. Those evaluations still require explicit execution with the established shared spending limit and retained evidence.
- **Production:** deployment, production proxy verification, durable usage accounting and backups remain later rounds. This workflow does not release or deploy the application.

## 7. Verification

| Check | Actual result and limits |
| --- | --- |
| Official action reference/input review | Passed: all three refs resolved to the recorded full commits, and used input names exist in their pinned action metadata. |
| Dedicated workflow validation | **Passed** with actionlint **1.7.12**, after checking the official release archive's SHA-256 against its checksum manifest. |
| Clean Linux dependency installation | **Passed**: Python/uv and npm installed locked dependencies in separate fresh source copies. No local virtual environment, `node_modules`, `.next` cache or `.env` was mounted. |
| Backend lint/format | Passed; all **95 Python files** passed format checking. |
| Fresh database migration | Passed: revision `12fdf9646b5d` applied from an empty temporary database. |
| Migration/model agreement | Passed: `alembic check` reported no new upgrade operations. |
| Backend offline suite | **360 passed in 3.05 seconds** in Linux. |
| Actual PostgreSQL/Redis integration suite | **45 passed in 6.41 seconds** in Linux, with dedicated temporary services. |
| Frontend lint/native tests | Passed; **11 tests passed** using Node **24.22.2** in Linux. |
| Fresh production build | Passed: Next.js **16.4.2** compiled, TypeScript passed and both locale home/detail routes built without a backend server. |
| Exit states and cleanup | Both job-equivalent containers exited **0**. The temporary database had zero leftover test schemas and Redis had zero keys. All four owned containers, their temporary anonymous data volumes and the owned network were removed after label/identity checks. |
| Application/secret review | Final scope is three files; application/dependency/deployment source is unchanged. No configured sensitive values or new attribution were found in the changed content. |

This is **local Linux command-level verification**, not an executed GitHub-hosted workflow. The local containers are Debian-based (`python:3.12-slim` and `node:24-bookworm-slim`), while the configured hosted runner is Ubuntu 24.04. Runner action downloads, GitHub cache transport, event/concurrency behavior and hosted service-port mapping were reviewed/validated but have not been observed in a real hosted run. The first actual hosted run must be checked after the user authorizes uploading this round. No green hosted check or CI badge is claimed.

An initially requested composite uv/Python image tag was unavailable. The local verification used the official Python base image and installed the same verified uv **0.12.15** release from PyPI instead; no workflow version, application dependency or lockfile was changed to bypass that setup issue.

The isolated source archive contained **188 files**, limited to tracked backend/frontend source plus the new workflow. Logs and a verification receipt were retained outside the repository in a temporary task directory. Backend verification finished at **2026-11-09 18:55:09 UTC**; frontend verification finished at **18:55:35 UTC**. The final workflow's LF-normalized SHA-256 is `0515554dd513b10971417904fd075c59ca7be15c9b9c85a36b62ad63a5067124` (the final completion check verifies the exact digest).

Expected nonfatal messages include the existing Node module-type warning and a cold Next.js build-cache notice. They did not suppress checks or turn failed tests into successes. The normal project's PostgreSQL, Redis, backend and frontend were not stopped, reset or used by these isolated checks.

No new UI/browser sweep, production deployment, paid-model call or live 20-query recommendation gate was performed: this round changes CI/documentation only. No verification is relabeled as a live recommendation-quality result.

## 8. Approvals and remaining work

The user authorized publishing/merging Update 15 and continuing with the next task. CI is already required by the specification and was proposed as the next round before implementation. No major architecture, provider, schema, core capability, privacy or spending decision was introduced, and no further approval was needed for these bounded implementation choices.

This new workflow remains local and awaits its own upload confirmation. After confirmation, push this reviewed branch and inspect its first GitHub Actions run before any separately authorized main merge. Do not treat the successful local reproduction as a substitute for that first hosted result.

Remaining project work includes durable budget operations/backup recovery, documented storage/specification gaps, full deployment packaging/proxy setup, UI/documentation polish, public deployment and final user testing. Branch protection is a separate administrative setting and was not changed here.

## 9. GitHub submission

**Proposed commit title**

`ci: add reproducible backend and frontend checks`

**Proposed commit description**

Lumen relied on manual verification and had no GitHub checks. Add independent backend and frontend jobs for pushes, pull requests and manual runs, with pinned actions, locked installs, read-only checkout permissions and cancellation of superseded runs.

Run Python lint/format checks, fresh Alembic migrations/model comparison, offline tests and native PostgreSQL/Redis tests against temporary services. Run frontend lint, native tests and a production build with TypeScript checks. Keep project API keys empty and live AI evaluation separate, preserving the daily 100-attempt policy. Document required-check configuration and the distinction between local reproduction and hosted execution. No application code, dependencies, schema or deployment behavior changes.

Validation: actionlint 1.7.12 passed; official action commits/inputs were verified. Fresh isolated Linux runs passed 360 backend tests, 45 database/cache tests, 11 frontend tests, both linters/format checks, migrations/model agreement and production compilation. Both job-equivalent containers exited zero and temporary resources were cleaned. The GitHub-hosted workflow has not run because this round is not uploaded; verify its first run after upload approval. No live recommendation gate or deployment is claimed.

See `update_version/Lumen_Update_Version_16.md` for exact tools, files, local evidence, hosted-run limitations and remaining work.

**Actual status:** local, uncommitted implementation on `codex/update-16-continuous-integration`. No Update 16 upload, pull request, main merge, release or deployment has been authorized or performed. The user's preceding authorization covered publishing/merging Update 15 and implementing this next round.
