# Round 25 follow-up acceptance review

Date: 2026-11-13, Europe/Madrid. Branch:
`codex/update-25-reading-intent-and-latency`. Baseline: `d5642f3`.

## Complete captures retained

| Capture | Shared attempts | Actual outcome |
| --- | --- | --- |
| `eval-live-20261113-round25-followup.json` | 0 to 62 | Twenty requests completed. Spanish history returned only three books. All 18 applicable first-book timings passed; two nonsense cases were inapplicable. Manual review found travel-form false positives. Gate failed. |
| `eval-live-20261113-round25-subjects.json` | 62 to 117 | Twenty requests completed. An overly restrictive comics subject label produced no Spanish manga results. Nineteen cases passed; the empty normal case was blocked by that evaluator revision. Gate failed. |
| `eval-live-20261113-round25-final.json` | 117 to 171 | Twenty requests completed. English comics returned four books after both retries. All 18 applicable timings passed; two nonsense cases were inapplicable. Other five checks passed for all cases. Gate failed. This filename does not identify the current source revision. |

No report was overwritten. Subsequent source changes invalidate these captures
as a complete gate for the final code. Offline replay
`reading-form-replay-20261113-round25-current.json` now flags all four old English
comics selections under the strengthened reason/form rule. It makes no service
calls and blocks old first-book timing as new evidence.

## Supplementary probes retained

These are deliberately marked `full_suite: false` and `gate_passed: false`.
Their local single-case checks cannot replace the complete gate.

| Capture suffix after `eval-supplementary-20261113-round25-` | Attempts | Books / first book | Interpretation |
| --- | --- | --- | --- |
| `comics.json` | 171 to 177 | 4 / 11,972 ms | Larger retrieval pool and literal subgenre anchoring alone did not solve coverage. |
| `comics-enriched.json` | 177 to 181 | 6 / 10,257 ms | All automated checks passed, but manual review found ordinary comic strips, a critical compilation and prose-fiction substitution. Not a semantic success. |
| `comics-evidence.json` | 181 to 186 | 2 / 10,054 ms | Positive form/subject evidence rejected the substitutions; the overly broad catalog subject still left too few matches. Count failed. |
| `superhero-subject.json` | 186 to 188 | 8 / 7,506 ms | Specific catalog subject produced actual superhero/graphic evidence; all automated single-case checks passed. |
| `comics-current.json` | 188 to 190 | 7 / 7,568 ms | Final source revision. All six automated checks passed, using two logical calls and two actual attempts without broadening. |

The current probe contains only retrieved ISBNs and stored graphic/superhero
evidence. Earlier ordinary-strip and prose substitutions are absent. Catalog
classifications and the lexical rule still do not prove every requested theme:
the Animal Man descriptions explicitly discuss moral dilemmas, while some other
selected descriptions give a weaker thematic connection. Proper-word grounding
also does not establish complete factual entailment. Manual review and the
fresh complete gate remain necessary; no general semantic guarantee is claimed.

## Status when the 200-cap window closed

The user explicitly approved a temporary cap of 200. All eight runs above share
the original PostgreSQL singleton on UTC 2026-11-13: **0 to 190/200**, with no
manual reset, refund, cloned allowance or higher limit. The preceding UTC day's
100-attempt usage remains in earlier evidence; the database advanced by its natural rollover.
Only 10 attempts remain, below the minimum 38 model invocations for a fresh
uncached canonical run (18 ordinary requests need parse and rank; two nonsense
requests need parsing). Provider retries and broadenings can require more.

No new full run is started with that insufficient allowance. The default cap
remains 100; temporary process configuration is removed at the end of the
window without lowering the actual count. Round 25 remains local, uncommitted,
not uploaded, not merged, and without a passing complete live gate.

## Separately authorized 300-cap continuation

The user subsequently approved a temporary 300 ceiling on the same 190-attempt
floor, conditional on full acceptance before merging. The separate final capture
`eval-live-20261113-round25-merge-gate.json` now completes all 20 canonical
requests with `gate_passed: true`: all five non-latency checks pass 20/20;
18 first-book timings pass and two nonsense timings are inapplicable. The maximum
first-book measurement is 9,701.89 ms. All 144 delivered cards are retained.

Observed use is 190 to 234/300, matching 44 reserved actual attempts and 44
logical calls. No case exceeds six logical calls or two broadenings. Nineteen
cases miss the complete-result cache; `en_comics` is an explicit hit, backed by
the source-identical real current probe above. Shared parse/catalog caches are
not fully tracked; this is not a fully cold-run claim. None of the 14 distinct
previous bad-snapshot ISBNs in the regression fixtures is selected.

The default 100 policy was restored without lowering 234. Temporary services
were removed and original volumes preserved. The complete current-source gate
now passes, but semantic heuristics and the public-release boundary still apply.
Remote checks and authorized main synchronization are recorded subsequently in
the next implementation record. The previous failed captures and their outcomes
remain unchanged.
