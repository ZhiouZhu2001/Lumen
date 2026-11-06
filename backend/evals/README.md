# Recommendation evaluation

This suite implements the six automated checks in specification section 9.
It contains 20 distinct queries: 10 English and 10 Spanish. Both languages cover
broad genres, publication-era and length constraints, comics, free books, niche
requests and one nonsense input.

## Running the suite

From the repository root, use `make eval`. The equivalent command from `backend/`
is:

```console
uv run python -m evals.run --live
```

Use the existing backend environment configuration, including its model and API
credentials. The live command makes real model and bibliographic API calls. It
runs queries sequentially, with a 60-second timeout per query by default. Change
the timeout with `--timeout SECONDS` if needed; this does not change the
15-second first-book requirement.

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
| Links | Each book has a buying or reading link on a known HTTPS store host. Spanish-only stores cannot appear on English requests; Norma Comics requires comic, manga or graphic-novel metadata; free-only requires a Gutenberg link. |
| Reason | A reason and source description exist. Capitalized words outside sentence starts must occur in the title or description, with accent normalization and an exception for the pronoun `I`. |
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

## Current integration boundary

The live runner currently invokes the recommendation graph, not the HTTP search
endpoint. The existing HTTP endpoint still returns keyword-search JSON. The
graph has no final book-card/store-link adapter, no HTTP SSE timing measurement
and no request-filter support. Reports list these gaps explicitly. Requested
filter fields remain visible as unsupported; they are not silently discarded
or represented as implemented by rewriting the query.

Consequently, the current full-suite run cannot pass the merge gate. Preserve
the feature branch until the missing product integrations and any observed
failures are resolved and a new full live run actually passes. Do not weaken
criteria or substitute graph duration to obtain a green result.

When those integrations exist, extend the runner to consume their actual output.
`evaluate_case` already accepts a per-ISBN list of `EvalLink` values and a measured
`first_book_sse_ms`. These parameters are evidence inputs, not simulated values
to supply to a live run. Filter support must also be connected and verified
before removing its unsupported status.

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

To recheck a complete version 2 capture offline, run from `backend/`:

```console
uv run python -m evals.replay evals/results/REPORT.json
```

Replace `REPORT.json` with an actual saved filename. Replay reconstructs candidate
and recommendation evidence and runs the current checks without model or catalog
requests. It does not rerank books, test a new prompt, or measure new latency. The
current capture has no links/SSE observations, so replay retains those blocked
checks and exits with `1`. It does not modify the original report. Reproduction
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
