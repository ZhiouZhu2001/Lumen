# Live recommendation acceptance

The release evidence is the complete 20-query English/Spanish HTTP suite with
all six checks. Offline tests, a successful build, a health check, a synthetic
stream probe or a historical passing report cannot establish current live
recommendation quality and first-book latency.

## Prepare the existing runtime

1. Obtain authorization for real model/catalog calls and their possible model
   charges. Keep the existing 100-attempt UTC-day allowance. Upload and public
   deployment authorizations are separate.
2. Identify the intended existing PostgreSQL database and Redis instance. Keep
   the original daily ledger; a disposable integration-test database is never
   an alternative live allowance. Stop incompatible older workers before using
   their original data volumes. Do not enable previously stopped wildcard host
   bindings merely to run a local evaluation.
3. Run the read-only readiness diagnostic described in `operations.md`, retain
   its safe result, and make a verified private application backup. Readiness
   does not authenticate provider credentials or reserve future allowance.
   Backups contain private reader data and must remain outside Git.
4. Build and start the real frontend with a loopback-only backend target and no
   backend keys in its process environment. Reserve an unused loopback backend
   port for the evaluator. The frontend must actually forward to that port.

For example, build/start the frontend with
`BACKEND_URL=http://127.0.0.1:8034`, listening on `127.0.0.1:3034`. With the backend
environment pointing to the existing data services, run from `backend/`:

```console
uv run python -m evals.run --live --isolate-hourly --frontend-url http://127.0.0.1:3034 --backend-port 8034 --output evals/results/<unused-report>.json
```

Use a new output path every time and retain failures. A nonzero exit is evidence,
not permission to relax thresholds. Stop only the temporary processes/resources
created for this run. Preserve original databases, volumes, private backups and
daily accounting when returning to the previous service state.

## Interpret budget and cache evidence

`--isolate-hourly` changes only the evaluation server's expiring Redis IP-counter
namespace. Each namespace still admits at most 20 searches per IP per hour. All
namespaces use the same production `DailyBudget` object and PostgreSQL singleton;
a new namespace cannot grant new model attempts. No original hourly key is
deleted. This is test admission isolation, not a product policy change.

The report records the initial and latest read-only budget snapshots and the
known same-UTC-day difference. Unknown reads stay unknown; rollover is marked
explicitly. The shared difference can include other workers. Per-case diagnostic
counts distinguish logical model invocations from actual transport reservations,
including retries. Reservations can conservatively exceed actual provider sends
after a crash, and neither failed requests nor aborted tests are refunded.

Shared complete-result, parsing and catalog caches remain in place. Per-case
`result_cache_hit` describes complete-result reuse only. A null value means no
captured evidence. A false value does not prove cold parsing or catalog access.
Do not present these timings as cold-cache performance without separate evidence.
The report identifies the actual source through fingerprints even on an
uncommitted branch. Keep source files unchanged during the run.

## Interpret quality, latency and store links

Every case retains candidate membership, language, count, link-rule, reason and
latency evidence. Nonsense inputs require no books and have no applicable
first-book timing. Ordinary queries require 5–10 books. Niche cases may return
1–4 only after both broadenings; all their constraints remain, including the
two explicitly reclassified Spanish-author/decade/short-length cases.
The 15,000 ms first-book threshold does not increase with a longer test timeout.
Metadata matching and reason grounding remain conservative heuristics and need
human review for full semantic relevance.

The frontend target measures receipt through the actual native Next.js proxy.
Loopback results do not establish public DNS/TLS, Caddy, browser layout, load or
future provider availability. An empty, denied, failed or timed-out search must
not become a successful zero-result recommendation through missing evidence.

HTTPS host and store-rule checks establish link construction, not inventory,
prices or destination availability. A bounded read-only probe of emitted links
can record status, redirect destination and failures. A 403/429 or bot challenge
is unverified; it is not proof that a book is unavailable. Do not bypass access
controls or label a challenge page a working product page. Manually inspect
unverified store destinations before public release.

## Release boundary

Keep the suite, six checks, fixed graph, two-broadening limit and daily budget
unchanged when diagnosing a failed capture. Subsequent prompt/retrieval changes
need a new complete passing gate; replaying stored timing is not a new live
measurement. Review the selected books independently of aggregate pass counts.
Production activation still requires the host/domain, backup destination,
deployment proposal and explicit first-release approval described in
`production-deployment.md`.
