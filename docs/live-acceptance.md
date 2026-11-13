# Live recommendation acceptance

The release evidence is the complete 20-query English/Spanish HTTP suite with
all six checks. Offline tests, a successful build, a health check, a synthetic
stream probe or a historical passing report cannot establish current live
recommendation quality and first-book latency.

Before relying on a retained complete capture, run the file-only
[acceptance evidence audit](acceptance-evidence.md). It verifies source/suite
identity, delivery, replayed non-latency checks and stored timing/accounting
consistency without new calls. Its result does not replace a new live run after
behavior changes or establish public-release approval.

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

## First-card optional channel deadline

The first uncached card gives optional store lookup at most one second, reduced
to the remaining 15-second first-book budget minus a 250 ms transport margin.
The deadline includes provider-lock and request-spacing waits. If no time
remains, optional work is not started. A completed fast lookup is still included;
an unfinished lookup is cancelled and recorded as `unavailable`, not `not_found`.
Static ISBN search links remain on the card. Timed-out work does not seed a
negative lookup cache, and later calls retain the existing Apple request-spacing
policy. Outer search/client cancellation still propagates normally.

This changes no SSE fields or event ordering. There is no hidden background
lookup or later link-update event. Later cards keep the existing optional lookup
behavior within the overall 60-second stream deadline. A slow graph can still
miss 15 seconds before card construction starts; the cap is not a guarantee of
every live first-book measurement. A fresh complete live gate is still required.

## Release boundary

For an explicitly approved temporary acceptance window, an operator can set
`DAILY_AI_CALL_CAP=200` (or 300 only with separate explicit approval) in the
evaluation backend's process environment and check the matching declared policy
with `python -m scripts.check_runtime_readiness --expected-daily-cap 200` or
`--expected-daily-cap 300` respectively.
The diagnostic compares the configured cap with that declared expectation; it
does not change configuration, initialize usage or reserve allowance. Without
the explicit argument it continues to expect the standard cap of 100. Every
attempt still uses the original PostgreSQL singleton and the database's UTC day.
An hourly test namespace never grants another daily allowance.

Restore the process policy to 100 after the authorized window and retain the
actual cumulative count. If usage already exceeds 100, new uncached work remains
blocked until the normal UTC reset; do not lower the row or refund attempts.
Temporary cap approval is not upload, release or deployment approval.

Keep the suite, six checks, fixed graph, two-broadening limit and daily budget
within its explicitly approved policy when diagnosing a failed capture. Subsequent prompt/retrieval changes
need a new complete passing gate; replaying stored timing is not a new live
measurement. Review the selected books independently of aggregate pass counts.
Production activation still requires the host/domain, backup destination,
deployment proposal and explicit first-release approval described in
`production-deployment.md`.

Retain failed full captures and supplementary probes separately. A single-case
probe can pass all six automated checks and still fail manual semantic review;
it never establishes the complete 20-case gate. Any later source change needs a
fresh gate, even when an earlier filename contains `final`. Do not combine cases
from different revisions into a passing result. If the approved remaining daily
allowance cannot support a complete uncached run, retain the failure/pending state
and obtain further explicit authorization or resume after the natural UTC reset.
