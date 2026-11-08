# Recommendation evaluation

This suite implements the six automated checks in specification section 9.
It contains 20 distinct queries: 10 English and 10 Spanish. Both languages cover
broad genres, publication-era and length constraints, comics, adventure classics, niche
requests and one nonsense input.

## Running the suite

From the repository root, use `make eval`. The equivalent command from `backend/`
is:

```console
uv run python -m evals.run --live
```

To measure the real frontend entry point as well, leave the frontend running,
stop the standalone backend that occupies its configured port, and run:

```console
uv run python -m evals.run --live --frontend-url http://127.0.0.1:3000 --backend-port 8001
```

The evaluator starts its privately observed backend on that fixed loopback port;
the running frontend must already forward there. It closes the evaluation server
after completion, so restart the normal preview backend afterwards. The optional
frontend origin is limited to loopback HTTP. There is no fallback to a direct
backend measurement when the frontend path fails. Reports identify the target,
first event timing and observed response encoding separately.

Use the existing backend environment configuration, including its model and API
credentials. The live command makes real model and bibliographic API calls. It
runs queries sequentially, with a 60-second timeout per query by default. Change
the timeout with `--timeout SECONDS` if needed; this does not change the
15-second first-book requirement.

The HTTP evaluator uses the application's real Redis caches, hourly search limit,
daily model-request cap and PostgreSQL persistence. Twenty queries consume the
entire per-IP hourly allowance; repeated runs can legitimately receive 429s.
For an isolated evaluation, select an empty dedicated local Redis logical
database through the process environment, keep the same active policy settings,
and retain that isolation and the resulting counters alongside the report.
Actual provider attempts from an isolated test database must also be charged to
the normal shared daily allowance when the same credentials are used. Retain a
one-time reconciliation receipt and before/after counts; do not send additional
model requests or reset existing counters to perform that accounting.
Never clear interactive usage keys or raise the cap to hide a denied run. A cold
run means no initial evaluation cache entries, while repeated catalog parameters
within the run may still benefit from the specified caches. Full result hits do
not establish new model execution. The graph-only diagnostic does not pass
through HTTP admission or the guarded provider transport and is not a substitute
for this HTTP gate.

To check query coverage without network calls:

```console
uv run python -m evals.run --validate-only
```

Validation-only success means the query file is valid. It is not an evaluation
pass. The offline pytest tests use test doubles and do not replace a live run.

## Checks and evidence

| Check | Evidence and criterion |
| --- | --- |
| Authenticity | Every selected ISBN is a unique, valid ISBN-13 in that search's retrieved candidate list. |
| Language | Every selected candidate's language matches the requested language. |
| Count | Normal queries return 5–10 books; nonsense inputs return zero. A niche query may return 1–4 only after both broadening retries are exhausted. |
| Links | Each book has a buying or reading link on a known HTTPS store host. Spanish-only stores cannot appear on English requests; Norma Comics requires comic, manga or graphic-novel metadata; retired free-only cases retain their original Gutenberg requirement in historical replay. |
| Reason | A reason and source description exist. Capitalized words outside sentence starts must occur in the title or description, with accent normalization and an exception for the pronoun `I`. Explicit concessions that a requested term is absent are rejected. |
| Latency | A real HTTP SSE first-book measurement is at most 15,000 milliseconds. Total graph execution time is recorded separately and cannot satisfy this check. |

The proper-word check is a simple heuristic, as required by the specification.
It can miss unsupported facts expressed without capitalized words or at sentence
starts, and can flag ordinary capitalized words. It does not prove semantic
grounding. Link host/rule checks do not prove that a store stocks a book or that
a URL template works; the specification's manual store-template verification is
still required when channels are implemented.

The same unchanged proper-word heuristic now lives in `app/grounding.py` and is
also applied before accepting production picks. The approved 2026-11-06 flow
retries after ranking when fewer than five validated recommendations remain,
up to two broadenings and six logical model invocations. Valid earlier picks
are retained. Failed normal-query counts still fail this suite after the budget
is exhausted; the fallback is not a waiver of the evaluation requirement.

Individual results use `pass`, `fail`, `blocked` or `not_applicable`. Missing
product evidence is `blocked`. Only first-book latency for nonsense input is
`not_applicable`, because such input must produce no book. A provider failure or
timeout blocks all checks for that query; it is never counted as a successful
zero-result response.

## HTTP integration and approved scope

The default live runner starts a real loopback Uvicorn HTTP server using the
production lifespan, search route, graph and book-card builder. It consumes the
actual POST SSE response and measures first-book receipt using the client clock.
A private in-process observer retains candidate evidence; no audit endpoint or
private state is exposed to the browser. Wire cards and done counts are checked
against captured cards. Publication-decade/page-count constraints are checked on
every returned card; genre participates in semantic retrieval and ranking.

On 2026-11-08 the user approved temporarily removing free-only reading and its
corresponding evaluation scope because Gutendex search remained unavailable.
The suite remains 20 distinct cases, ten per language, with all six checks.
Ordinary adventure-classics queries replace the two free-only cases; they make
no free-availability claim. The original suite is retained byte-for-byte at
`history/queries-update9.yaml`. A second user approval classifies the English and Spanish
Spanish-author/decade/short-length queries as niche. Their constraints remain
unchanged; 1–4 books are accepted only after both retries and the UI must explain
that fewer matches were found. Other normal queries still require 5–10. The
strict-count suite used by the first two Update 10 HTTP captures is preserved at
`history/queries-update10-strict.yaml`; use that file to replay those reports. Old reports are not rewritten. Replaying an old
capture requires `--suite evals/history/queries-update9.yaml`.

Use `--graph-only` to retain the previous graph/card diagnostic runner. That mode
still reports missing HTTP latency and unsupported request filters; its results
cannot establish a passing HTTP gate. No latency threshold, ordinary normal-case count target, ISBN membership check,
grounding heuristic or retry budget has been relaxed. The two explicitly approved
case reclassifications are the count-scope exception described above.

The HTTP capture targets one backend process on loopback. It is not a production
load test, public deployment, or a guarantee of future provider uptime. Browser
proxy behavior is verified separately in the local preview.

## Reports and exit status

Each live run creates a timestamped JSON file under `evals/results/`. An explicit
unused path can be supplied with `--output PATH`. Existing reports are not
overwritten by the command.

The report includes the suite SHA-256, model name, Git baseline and dirty-tree
status, individual queries, selected books/reasons, candidate ISBNs, retries,
workflow durations, check explanations and aggregate counts. It contains no
credentials or raw provider exception messages. A failed graph invocation has
unknown candidates and retry counts, rather than fabricated empty evidence.

Version 2 reports also include SHA-256 fingerprints of the backend application
and evaluation Python files, normalized candidate snapshots, the latest parsed
query, the number of candidates with usable descriptions, the shortlisted ISBNs
and the formatted catalog input supplied to ranking. Snapshots retain the full
source description so reason checks can be reproduced; `ranking_input` records
the existing 600-character description limit and 30-book limit. Cover URLs and
raw provider payloads are excluded from these snapshots. The fingerprints identify
the evaluated source even when its working tree has uncommitted changes.

After the approved ranking-feedback change, reports also contain `model_calls`
and `ranking_rounds`. Every round retains its actual priority shortlist, formatted
ranking input, proposed picks, accepted picks and validation feedback. The
top-level shortlist/input comes from the final actual round, not a reconstruction
of the first 30 accumulated candidates. `model_calls` counts logical structured
model invocations, not catalog requests or transport retries within a provider SDK.

Initial parsing now declares whether the input has meaningful reading intent.
Unintelligible input returns zero picks without catalog calls or broadening;
it is not converted into a generic reading request. This is a model-based intent
decision, not a hardcoded list of evaluation queries. Old parsed-query snapshots
remain readable because the new field defaults to a meaningful request when
absent.

Channel-enabled captures retain cards, per-ISBN lookup statuses, channel errors
and a separate `channel_duration_ms`. Console durations still report graph time;
channel lookup time is additional and may include Apple's request-spacing waits.
The existing per-case timeout bounds the graph plus channel attachment. A channel
timeout or invalid card input preserves graph evidence and blocks the link check.
Provider outages are `unavailable`, rather than authoritative no-match evidence.
Source fingerprints now also include `app/stores.yaml`.

To recheck a complete version 2 capture offline, run from `backend/`:

```console
uv run python -m evals.replay evals/results/REPORT.json
```

Replace `REPORT.json` with an actual saved filename. Replay reconstructs candidate
and recommendation evidence and runs the current checks without model or catalog
requests. It does not rerank books, test a new prompt, or measure new latency. The
replay uses links only when cards were actually captured; old captures retain
their missing-link status. Replay deliberately does not treat retained timing numbers as new live HTTP
evidence; its latency checks remain blocked and it exits with `1`. It does not modify the
original report. Reproduction
of a check failure is useful diagnostic evidence, not a new live-service test.

Legacy version 1 reports contain only candidate ISBNs and cannot reconstruct
description/language evidence. Replay rejects those reports, partial reports,
missing snapshots, duplicate cases and mismatched suite/query metadata. Historical
reports remain unchanged; their absent snapshots are not filled with later API
responses, which might differ from the data originally evaluated.

An atomic checkpoint is saved after every query. Interrupted runs retain
`complete: false` and `gate_passed: false`. Only all 20 distinct expected cases,
with all six checks satisfied and no unsupported filters or workflow errors,
can pass the gate. The final report distinguishes completion from success:
`complete: true` means all cases ran, not that they passed.

The live command exits with `0` only when the merge gate passes, and with `1`
after a completed run with failures or blocked checks. Configuration or argument
errors also produce a nonzero exit. Retain unsuccessful reports as evidence;
later runs produce separate reports.

Constrained Open Library searches now include actual year/page-range parameters.
Up to eight validated work keys may supply missing catalog descriptions, with
three concurrent requests and two-second individual deadlines. Work descriptions
are shared only between already retrieved ISBN records linked to the same work;
no new recommendation identity is created. The work key stays internal and is
excluded from public card serialization. Captures retain attempted work keys.
Clear language-course substitutions are excluded using the original request
genre plus catalog/title/description cues, even if a broadening changes its genre.
This conservative heuristic does not independently prove nationality or full
semantic relevance. Manually inspect recommendations as well as the six checks.

Browser review also identified explicit topic-mismatch admissions in reasons.
Production ranking validation and the reason check now reject recognized English
and Spanish concession forms containing requested terms. Rejected ISBNs cannot
re-enter later ranking rounds by rewriting their reasons. Ordinary negation and
positive "not only" constructions remain allowed. This strengthens the gate;
it is still a lexical check, not a complete semantic entailment test. The earlier
passing Update 10 capture predates this refinement and remains unchanged. Use
`eval-http-20261108-round10-semantic-verified.json` for the later source revision.

A subsequent frontend-path probe exposed gzip buffering in the existing rewrite.
SSE responses now include `Cache-Control: no-cache, no-transform`, which prevents
the installed compression middleware from holding frames while preserving normal
page compression. `proxy-sse-20261108-round10.json` retains the failed 27.6-second
frontend observation. The final end-to-end capture is
`eval-frontend-20261108-round10-final.json`; earlier backend-only passing reports
do not establish frontend delivery timing.

For exact-byte replay of the currently approved cases, use
`--suite evals/history/queries-update10-approved.yaml`. Git attributes preserve
all historical suite bytes, including the original newline representation.
