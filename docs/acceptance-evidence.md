# Retained acceptance evidence audit

Use the file-only audit to check that a saved complete HTTP acceptance capture
still matches the current recommendation code and canonical 20-case suite:

```console
cd backend
uv run python -m scripts.check_acceptance_evidence --report evals/results/eval-live-20261113-round25-merge-gate.json
```

Add `--output evals/results/<unused-audit-name>.json` to retain a new audit result.
Exit 0 means the retained evidence verifies; exit 1 means it does not, or the
requested output cannot be created. Output creation is exclusive: existing
captures, audit files and input paths are never overwritten. Errors use fixed
codes without echoing raw payloads or exception messages.

## What verifies

- A completed version-2 HTTP capture with runtime evidence, exactly the canonical
  20 unique cases, matching query/language/category/filters, a passing gate and
  consistent six-check summary. Graph-only, partial, failed and supplementary
  probes do not qualify.
- The complete current application/evaluation source inventory and canonical
  suite identity. SHA-256 matches either raw bytes or uniform LF/CRLF variants;
  this permits Git's cross-platform text checkout conversion. Other whitespace,
  code changes, missing files or a different suite still fail. Captures and their
  original hashes are never rewritten. Source matches requiring this conversion
  are listed explicitly.
- Replayed authenticity, language, count, link and reason checks against the
  captured books. Saved pass labels alone are insufficient. Cards,
  recommendations, streamed book frames and the final total must agree. Workflow
  failures, unsupported filters and unexplained wire errors fail verification.
- Retained finite first-book timings within 15 seconds, with the intended
  nonsense exceptions and consistent HTTP duration. This checks old timing
  evidence; it does not measure a new first book.
- Same-UTC-day shared-budget evidence, observed attempts matching the usage
  delta, six-call/two-broadening bounds and explicit complete-result cache flags.
  A fully cached result cannot claim new model attempts. Cross-day or missing
  accounting cannot be verified by this version.

The result includes both the raw input checksum and its LF-normalized checksum,
so the same JSON data remains identifiable after Git newline conversion. These
checksums are not signatures. The model identity is retained as a digest; the
tool does not read runtime settings or grant any spending allowance.

## Boundaries

The audit reads files only. It makes no model/catalog/network/database calls,
reserves no allowance, changes no cache, and starts no service. It can run with
blank keys and disconnected networking. It neither reruns searches nor proves
that a consistently forged capture came from a trusted evaluator; protect the
original capture and review its history.

`verified` means the retained evidence is internally consistent and matches the
current source under the stated newline rule. It does not verify the currently
configured model, provider credentials, quota, current catalogs, public ingress,
production load or every semantic reading requirement. Individual catalog/parse
cache reuse is not fully tracked, and a cache-aware capture is not a cold-run
claim. A later prompt/retrieval change still needs a fresh full live gate.

Source identity covers the existing evaluator inventory: application Python,
evaluation Python and `app/stores.yaml`. It does not fingerprint frontend code,
dependency locks, migrations or deployment/runtime configuration. There is no
age-based freshness guarantee: even an identical-source capture can be old while
catalogs or external conditions have changed.

Use the separate [runtime readiness diagnostic](operations.md) for local service
prerequisites and the [live acceptance runbook](live-acceptance.md) for new
measurements. Upload, main synchronization and public release remain separate
authorization decisions; this audit approves none of them.
