# Round 25 live review and remaining limits

Date: 2026-11-12, Europe/Madrid. Source:
`eval-live-20261112-round25-reading-form.json`. The source contains the actual
native frontend-proxy run, candidate descriptions, selections, source fingerprints
and shared-budget evidence. The round-24 capture and its offline recheck remain
unchanged. This review does not turn automated passes into a general semantic
quality claim.

## Improvements established separately from live aggregate counts

The six concrete round-24 type mismatches and its direct history-versus-fiction
concession are rejected by offline regression tests at the production validation
seams. A stalled actual mock HTTP transport no longer prevents the first card,
while a fast matched optional store link remains available. These deterministic
tests establish those specific corrections; the following live run is additional
evidence and remains subject to the unchanged full acceptance requirements.

The new `en_fantasy` first book arrived at 8,167.46 ms, compared with 16,610.93 ms
in the earlier capture. The selections, live provider responses and possible
catalog-cache reuse differ, so this is not a controlled causal performance
comparison or a claim that every query improved. The new `en_short_modern`
measurement was still 16,502.65 ms and failed the unchanged 15,000 ms threshold.
Sequential parse/broadening/ranking work can consume the budget before optional
card enrichment begins.

## Remaining semantic false negatives

Manual review of the new selections found further type mismatches that the
current conservative heuristic did not reject. These are release-blocking
findings, even if the corresponding automated reason/type check passed.

| Case | Selected title and ISBN | Evidence in the captured catalog |
| --- | --- | --- |
| `en_comics` | *A Philosopher Reads...Marvel Comics' Civil War*, `9781910780114` | The Philosophy category and commentary framing indicate a discussion of superhero ethics; this does not establish the requested graphic-novel format. |
| `en_comics` | *Superhero Thought Experiments*, `9781609386559` | The description explicitly examines and analyzes superhero comic plots through a philosophical lens; it is commentary about comics, rather than the requested comic narrative. |
| `en_comics` | *A View of Ethics in Alan Moore’s Comic Books "Watchmen"*, `9783346370419` | The description explicitly presents an essay about the characters and ethics of a graphic novel. Calling its subject a graphic novel does not make the essay one. |
| `en_classics` | *A Narrative Of The Expedition To Dongola And Sennaar*, `9789359956817` | History metadata and the description present a military expedition account. Topic overlap with travel/exploration does not establish a classic adventure novel. |

Some other candidates have generic publisher boilerplate rather than useful
book-specific descriptions. This review does not infer their fictional form,
historical authenticity, setting or audience solely from a title. They need
independent catalog/manual evidence. No book metadata was invented to fill a
count requirement, and this round does not certify all other recommendations.

The present safeguard recognizes specific strong form cues and explicit
concessions. It deliberately retains ambiguous metadata. More varied forms of
analysis/essay/travel writing can therefore still pass. A subsequent correction
must cover these real counterexamples and preserve genuinely requested
nonfiction and valid historical/graphic fiction. Do not repair the reasons by
concealing a book's actual form, relax counts or increase retries to obtain a
passing report.

## Acceptance and authorization boundary

All twenty HTTP requests completed; the gate did not pass. Actual first-book
latency passed eleven cases, failed `en_short_modern` (16,502.65 ms) and `en_sea`
(15,076.13 ms), and was inapplicable to one completed nonsense input. Six other
timings were blocked. The daily ledger increased from 54 to **100/100**, exactly
46 reserved attempts; no additional outbound attempt was allowed. The
`es_classics` stream was interrupted with `rate_limited`, retaining four interim
graph picks but emitting no cards. The last five requests were refused with
HTTP 503 under the existing exhaustion policy; all their checks were blocked.
These are missing completion evidence, not successful zero-book results.

The final aggregate and known budget state are recorded in the source JSON and
`update_version/Lumen_Update_Version_25.md`. The user authorized at most
the original remaining 46 model attempts on UTC 2026-11-12. Exhausting that
allowance blocks further uncached model work rather than granting a new budget.
No cache-only rerun or stored timing replay can validate a later correction.
Another complete real gate is required before merging the changed recommendation
behavior; production release and upload approvals are separate.
