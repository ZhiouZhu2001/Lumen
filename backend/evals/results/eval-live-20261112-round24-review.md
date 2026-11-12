# Round 24 live acceptance review

Date: 2026-11-12, Europe/Madrid. Source:
`eval-live-20261112-round24-initial.json`, captured through the native Next.js
production proxy and real backend/model/catalog services. The source JSON retains
the exact candidate descriptions, selected reasons, application fingerprints,
checks, timing and accounting evidence. This review does not change that report,
the queries or the acceptance criteria.

## Semantic mismatches observed in the saved cards

These examples demonstrate content-type mismatches that the existing six-check
heuristics did not reject. They are evidence from this particular run, not an
exhaustive semantic certification of every other selected book.

| Case | Selected title and ISBN | Observed mismatch |
| --- | --- | --- |
| `en_fantasy` | *Baby Dragons Adult Coloring Book*, `9798704552857` | The request is for fantasy novels with an adventure story. The catalog describes a coloring/activity book. Shared dragon/adventure vocabulary does not make it a novel. |
| `en_classics` | *The British Expedition to the Crimea (Classic Reprint)*, `9780265740309` | The request is for classic adventure novels. The candidate describes a historical expedition account and has History metadata. A classic reprint is not necessarily classic fiction. |
| `en_classics` | *The Official Report of the Recent Arctic Expedition (Classic Reprint)*, `9781332025312` | The selected candidate explicitly presents an expedition report and Science metadata. Travel/exploration overlap does not establish the requested novel form. |
| `en_history` | *A Short History of the Spanish Civil War*, `9781848856585` | The request and explicit filter require historical fiction. Both catalog metadata and the selected reason identify history rather than a novel; the reason explicitly concedes the mismatch. The current lexical concession check missed this formulation. |
| `en_sea` | *The Novel and the Sea*, `9780691140650` | The request is for a sad literary novel. The description presents scholarship about the history of novels and maritime culture rather than the requested fictional narrative. |
| `en_sea` | *Shipboard Literary Cultures*, `9783030853419` | The catalog describes a collection of essays about literary practices at sea. Topic overlap alone does not satisfy a request for a novel. |

The selected books can be authentic, use the requested language, have valid store
links and contain reasons grounded in their descriptions while still being the
wrong type of reading. Count/ISBN/link success must not be presented as complete
recommendation quality. Nationality, precise setting and intended audience also
need review when catalog evidence is incomplete; this review does not invent
those facts from an author's name or a title.

## Timing observations

All 20 cases completed. Authenticity, language, count, link-rule and reason
heuristics passed for every case. First-book latency passed 15 cases, failed
three and was not applicable to the two nonsense inputs. The failed timings were
16,610.93 ms (`en_fantasy`), 17,152.19 ms (`en_short_modern`) and 15,614.80 ms
(`es_short_modern`). The gate therefore did not pass. The original shared daily
ledger and observed attempt counts both increased by 54; no separate allowance
was created. All 20 complete-result cache flags were false, while parsing and
catalog caches remained shared and were not fully tracked.

The 15,000 ms first-book threshold remains unchanged.
For `en_fantasy`, the observed first book arrived at **16,610.93 ms**. Local node
diagnostics place parsing at approximately 2.73 seconds, retrieval at 1.59 seconds
and ranking at 3.59 seconds. Their combined time is about 7.91 seconds, leaving
about 8.70 seconds before first-book receipt. The current stream awaits the first
card's optional channel lookup before sending it. This identifies a concrete
path for investigation; it does not attribute every millisecond to one provider
or establish the cause of every other failed case. Queries requiring both
broadening retries also have more sequential model work.

## Store destination observations

`store-links-20261112-round24.json` records seven bounded emitted-link samples,
one per store/language pair. All returned HTTP 200, including two Amazon samples
that needed GET headers after HEAD returned 405. These are header reachability
results only: no product relevance, stock or challenge-page content was checked.
The Abacus sample redirected to a URL carrying `noresults=true`; this is a visible
warning against treating successful HTTP status as a matching product result.
Norma Comics redirected to its current search path. No rule/template was changed
from this limited evidence, and no access control was bypassed. Manual destination
and stock checks remain separate release work.

## Recommended next implementation round

1. Preserve the reader's requested form through retrieval and ranking, and
   reject clear activity-book, nonfiction/report and literary-criticism
   substitutions for novel requests. Include these actual catalog snapshots in
   focused regression coverage. Do not expand this into an unsupported promise
   of complete semantic classification.
2. Cover explicit type/filter concessions in reasons, including the history
   versus fiction example. Reject conflicting candidates rather than rewriting
   their reasons to conceal the mismatch. Keep the existing candidate identity,
   structured-output and retry constraints.
3. Investigate the first-card optional-channel wait while preserving channel
   truthfulness, SSE compatibility and the provider's request-spacing policy.
   Keep the 15-second requirement and the complete gate.
4. After any prompt/retrieval correction, obtain authorization for any additional
   real calls and retain a new complete 20-case report using the same shared
   daily allowance. A cache-only rerun or offline replay cannot establish the
   changed behavior or new uncached latency.

No prompt, retrieval, product filter or streaming behavior was changed by this
acceptance round. The examples remain reproducible in the original failed
capture. Public release remains pending resolution and a new full passing gate,
independent of the normal upload/deployment approvals.
