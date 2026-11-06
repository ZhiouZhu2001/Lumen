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

An atomic checkpoint is saved after every query. Interrupted runs retain
`complete: false` and `gate_passed: false`. Only all 20 distinct expected cases,
with all six checks satisfied and no unsupported filters or workflow errors,
can pass the gate. The final report distinguishes completion from success:
`complete: true` means all cases ran, not that they passed.

The live command exits with `0` only when the merge gate passes, and with `1`
after a completed run with failures or blocked checks. Configuration or argument
errors also produce a nonzero exit. Retain unsuccessful reports as evidence;
later runs produce separate reports.
