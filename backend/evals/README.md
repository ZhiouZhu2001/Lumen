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
shared PostgreSQL daily model-attempt allowance and PostgreSQL persistence.
Twenty queries consume the entire per-IP hourly allowance; repeated runs can
legitimately receive 429s. To keep evaluation admission separate from interactive
IP counters, append `--isolate-hourly` to the HTTP command. This creates a unique
expiring Redis hourly namespace with the same 20-search limit. It retains the
original `DailyBudget` object, database and 100-attempt cap. Every outbound model
attempt, including a retry, is still reserved and committed in the same singleton
before sending. No later reconciliation or independent spending allowance is
created. Existing interactive keys and caches are not cleared or copied.

Never select a new PostgreSQL database, reset a ledger or refund failed attempts
to obtain more evaluation allowance. A temporary cap exception requires explicit
user approval and process-only configuration as described in the acceptance runbook.
Keep the normal daily budget
even when separating Redis test data. Full result hits do not establish new model
execution, and retained parse/catalog caches mean that a result-cache miss alone
does not establish a fully cold run. The graph-only diagnostic cannot substitute
for the guarded HTTP gate. See `../../docs/live-acceptance.md` for preparation and
the limits of these measurements.

To isolate cache/hourly test data while directly consuming the normal shared AI
counter, stop the regular backend and use an empty dedicated Redis database:

```console
uv run python -m scripts.run_isolated_eval --redis-db 14 --output evals/results/<new-report>.json --environment evals/results/<new-environment>.json
```

The helper copies only real cache entries for the current application version
and catalog caches, preserving TTLs. It never copies or clears IP counters, and
uses the unchanged production `UsageGuards` methods for both policies. The normal
PostgreSQL singleton remains the sole daily model-attempt counter, including retries.
The test database retains its own active 20-per-IP hourly policy. Both initial
cache hits and counter values are recorded; a cache-aware retry is not a cold
model-quality or latency claim. On Windows, a process-scoped execution request
temporarily inhibits idle system sleep during this bounded run and is restored
afterwards; no persistent power setting is changed.

The frontend uses a 70-second forwarding timeout to cover the backend's
60-second deadline. The first-book target remains 15 seconds. With the normal
backend stopped and the frontend running, verify delayed SSE without AI calls:

```console
uv run python -m scripts.check_proxy_stream --output evals/results/<new-proxy-probe>.json
```

This temporary diagnostic endpoint compares direct and frontend delivery across
a 35-second silent interval. Its report sets `full_suite: false`; it is not a
recommendation search, and its delay is not a first-book latency measurement.

To check query coverage without network calls:

```console
uv run python -m evals.run --validate-only
```

Validation-only success means the query file is valid. It is not an evaluation
pass. The offline pytest tests use test doubles and do not replace a live run.

## Checks and evidence

For a named-author request, the authenticity check also requires catalog author
metadata to match an independently declared `expected_authors` list, or the
original author constraint retained by the search. It remains one of the same
six checks; the required suite is still 20 cases with unchanged coverage/count
and latency requirements.

`author_queries.yaml` contains two supplementary named-author regressions.
Against the running local preview, execute:

```console
uv run python -m evals.author_run --output evals/results/<new-author-report>.json
```

These checks independently declare the expected author and inspect actual wire
cards, metadata filters, counts, ISBN checksums, stream completion and first-book
latency. Their reports explicitly set `full_suite: false`: they do not capture
private candidate membership and cannot replace the 20-case observer gate.
The original wrong-author cards must fail these author checks even though their
ISBNs are real and their date/length filters match.

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

Reading-form validation also rejects clear activity-book, nonfiction/report and
literary-criticism substitutes for fictional reading requests. It uses the
original query and retained request genre, including an explicit UI genre;
broadenings cannot replace that original requirement. The same predicate runs
before ranking and again before streaming, persistence and complete-cache reuse.
The reason check flags this mismatch independently of ISBN authenticity, and
direct English/Spanish type concessions are checked as well as the earlier
"although" forms. It does not certify complete relevance, nationality, exact
setting or audience. Explicit nonfiction requests and ambiguous fiction metadata
remain eligible; ordinary plot negation is not a type concession. The immutable
round-24 report and `reading-form-replay-20261112-round25.json` show why a real ISBN
and previously passing reason heuristic were insufficient.

The follow-up also rejects explicit essay/philosophical commentary and military
expedition-account cues while keeping genuinely requested nonfiction. Only
book-specific description evidence can support ranking and reasons: recognized
publisher/copyright boilerplate is removed from the model projection, while the
original catalog snapshot stays intact. HTML and escaped HTML are normalized
before this check. A boilerplate-only description is missing evidence, not a
usable synopsis. Candidate categories are supplied to ranking as catalog data;
they do not by themselves prove the form of the book.

Retained validated picks are supplied as already selected ISBNs, so the model
need only explain additional matches. If every usable shortlist entry is already
retained, ranking is skipped while the graph still executes its permitted
broadening/search stages. Reports retain the corresponding `model_called: false`
round rather than inventing a model call. The output still requires two short
grounded sentences and at most 30 candidate books.

Failed HTTP admission now retains only an allowlisted API error code from a
bounded response body. A `rate_limited` error is no longer relabeled as a generic
stream failure. Interrupted searches block all six checks. Top-level
`recommendations` describe actual delivered cards; unfinished selections are
separate `graph_recommendations` audit evidence. This prevents an interrupted
four-pick graph with zero wire cards from being described as four delivered books
with broken store links. Failed captures remain failed and are never overwritten.

The retained original genre now reaches both catalog clients on every search
round. Supported narrative-fiction genres add the catalogs' `subject:fiction`
constraint; graphic novels/comics use `subject:comics`. Existing language, author, year
and page constraints stay in place. Short-story collections keep their existing
catalog coverage because valid anthologies may be categorized as literary
collections rather than fiction. Manga retains or appends the literal `manga`
form word instead of imposing an English subject label that excluded actual
Spanish results in the retained intermediate run. Nonfiction requests receive no fictional
subject constraint. These catalog categories guide retrieval and are rechecked
by the production reading-form validation; a subject tag is not complete proof
of exact relevance. Explicit Travel classification without fictional evidence
cannot substitute for requested novels, while actual travel novels and requested
guides remain eligible.

The field syntax is documented by [Google Books](https://developers.google.com/books/docs/v1/using)
and [Open Library](https://openlibrary.org/search/howto/more). No source, query
count, broadening limit or extra model stage is added. A completed normal search
with genuinely zero results fails the count check; interruption/admission errors
remain blocked rather than becoming count or link defects.

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

HTTP reports with `runtime_evidence_version: 1` retain report format version 2
and add read-only budget snapshots before the run and after each completed case.
The final `budget_after` is the last such snapshot. `budget_delta` reports a
difference only for known, nondecreasing counts within one UTC day; unknown
storage, UTC rollover or a decreasing count cannot produce a claimed attempt
total. Concurrent workers may contribute to the shared difference.
Per-case `runtime_usage` contains observed logical model calls, actual reserved
transport attempts and complete-result cache reuse. `result_cache_hit` is null
when no observer evidence exists, rather than inventing a cache miss or zero
attempts. Reports also retain HTTP status and the actual hourly namespace and
cache policy. These diagnostics do not modify the six checks or authorize a
provider call; the durable ledger remains authoritative.

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

Narrative requests carry the original reading form into catalog subject searches.
An explicit superhero-comics request uses the more specific `subject:superheroes`;
exclusions and comparisons do not create a positive superhero requirement.
Supported narrative searches request up to 40 Google Books records in the same
HTTP request, while the ranker still sees at most 30. Manga and short-story
collections avoid an overly restrictive generic subject label. Manga keeps its
literal form word. An explicit superhero-graphic request needs catalog evidence
for both that form and subject in title, categories or usable description. This
stricter combined check can reject real comics whose captured metadata is too
sparse. Other ambiguous forms retain the conservative heuristic. These checks
do not prove every requested mood or moral theme.

Sparse graphic searches may fill missing or publisher-only descriptions after a
broadening: at most three verified work requests per retry, with the existing
eight-work global ceiling, three-request concurrency and two-second deadline.
Already supported form/topic metadata gets priority. Original catalog records
and the verified work payload remain separate provenance evidence. No ISBN or
synopsis is invented. Existing year/length-constrained enrichment keeps its bound.

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
