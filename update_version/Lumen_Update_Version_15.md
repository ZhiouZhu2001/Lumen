# Lumen Update Version 15

## 1. Basic information

- **Round:** 15, not an application release version.
- **Date:** 2026-11-09 (Europe/Madrid).
- **Branch:** `codex/update-15-catalog-refresh`.
- **Known baseline:** `6dd024c3e555928d3fbd0d2bdb1965f0054b314a`, verified on remote `main` and `codex/update-14-book-details` after the explicitly authorized upload and fast-forward merge.
- **Objective:** implement the specification's 30-day saved-catalog refresh requirement through the existing book-details read.
- **Actual scope:** bounded refresh on access, exact-edition reads from the existing providers, conditional metadata updates, safe stale fallback, tests and reproducible isolated live verification.

Update 14 was committed as `feat: add bilingual saved-book details and share links` and uploaded with its complete English description after the user's new authorization. Git author and committer were the verified project owner, `ZhiouZhu2001 <zhiouzhu2001@gmail.com>`. Both remote refs matched the full baseline above. No additional author credits, collaborators, pull request, release or production deployment were added. Update 14's historical local-review status is superseded by this publication record.

The working tree was clean before creating this new local branch. No unrelated user changes were present or incorporated. The maximum previous update number was 14; earlier records were not overwritten or renumbered.

## 2. Technologies used

No new dependency, framework, primary data provider, paid service or database schema was introduced.

- **Existing FastAPI lifecycle and book endpoint:** initialize a refresh coordinator with the already-owned repository, HTTP client, Redis connection and configured Google Books key. Invoke it only after an existing stored book has been read successfully.
- **Existing httpx and provider normalization:** perform a Google Books ISBN query and, when necessary, parse a specifically identified Open Library edition. These reads are separate from recommendation search, parsing and ranking. [Google Books documentation](https://developers.google.com/books/docs/v1/using) describes ISBN search; [Open Library documentation](https://openlibrary.org/dev/docs/api/books) distinguishes editions from works and documents ISBN-to-edition JSON resolution.
- **Python asyncio:** bound optional refresh to three seconds, limit in-process refresh concurrency to three, overlap the two provider reads and cancel unnecessary fallback work when the preferred provider succeeds.
- **Existing Redis `SET NX EX`:** coordinate one refresh attempt per ISBN across workers with a five-minute expiration. Failed attempts retain the cooldown. This namespace is independent of model spending and search-admission counters and contains no query or IP.
- **Existing SQLAlchemy/PostgreSQL:** update an existing book in a short transaction only while its ISBN, language and previously observed timestamp still match. No network request holds a database transaction open.
- **Existing pytest, native PostgreSQL/Redis fixtures and Ruff:** exercise exact identity, age boundaries, cancellation, failures, metadata preservation and concurrency.
- **A reusable Python diagnostic:** combine actual provider traffic with disposable local database/cache namespaces and record LF-normalized source hashes. This is catalog-refresh verification, not an AI recommendation evaluation.

## 3. Implementation

### Refresh policy

`GET /api/books/{isbn13}` retains its existing initial validation, 404 and sanitized storage-error behavior. Once a saved book exists, the refresh coordinator checks elapsed UTC time. A snapshot younger than 30 days, or one timestamped in the future, is returned without coordination or provider work. Exactly 30 days is eligible.

When a process has a free refresh slot, it attempts an expiring Redis lease for the ISBN. An existing lease, exhausted local slots or unavailable Redis returns the old book immediately or within the bounded attempt. The three-second deadline covers coordination, provider work and the conditional write together. Cancellation propagates and child provider tasks are closed; no background job or unbounded queue is created.

Fresh data can update the original response on the same read. Other simultaneous readers can receive their previously read stale snapshot while the admitted worker refreshes; a later read sees the stored result. The lease is retained for five minutes to avoid repeatedly calling a failing source. Unopened books are not periodically scanned: this is lazy refresh on access, not a scheduler or a claim that every database row is always fresh.

### Exact-edition identity

Google Books is queried with the saved ISBN, requested book language and a bounded five-volume response. Existing Google Books normalization is reused, and only the same canonical ISBN can be selected.

The Open Library fallback reads the ISBN JSON endpoint. Live investigation showed a 302 redirect to an edition JSON URL. The implementation accepts at most one HTTPS redirect on the same host to `/books/OL<digits>M.json`, rejecting credentials, nonstandard ports, query strings, another host or a work URL. A second redirect is not followed. The edition's own ISBN identifiers must contain the requested ISBN, and its own language references must contain the original language. A work listing multiple editions' ISBNs/languages is not sufficient.

Open Library descriptions, covers, page count, publication year and subjects are normalized conservatively. Its edition author IDs are not invented as names and do not trigger a chain of author lookups; existing names are retained when no complete new name list is supplied. No authority-ID resolution or new author-identity guarantee was added.

At most one Google request, one Open Library ISBN request and one permitted edition redirect are needed per admitted attempt; primary success cancels unnecessary fallback work. Each client read has a two-second timeout, inside the three-second overall refresh bound. Provider/API failures or unusable editions retain the saved book rather than fabricate a replacement.

### Safe persistence

`SearchRepository.refresh_book` revalidates candidate data and requires the original ISBN/language, an allowed source and an aware source-fetch timestamp newer than the observed snapshot and no later than the current time. It updates only an existing row. There is no insertion of an unsaved ISBN, no new search/result record and no migration.

Missing optional values preserve the previous metadata. Rating value/count/source remain a coherent tuple. Static channel rules are regenerated from effective metadata. A previously saved optional Apple Books title/author match is retained only while the effective title and author list remain identical; otherwise the unverified old match is dropped until a normal later search can establish one again. Refresh itself does not call Apple Books or any retailer.

The SQL update conditions include the previously observed `fetched_at`. A concurrent newer search or refresh wins; the delayed updater reads that current row rather than overwriting it. Failed or rejected refresh never advances `fetched_at`. A Google catalog-cache hit retains its actual earlier source-fetch time, not the time the detail page was opened. Retained optional fields may still be older than the source snapshot, consistent with existing metadata-preservation behavior; per-field freshness is not represented by the schema.

## 4. File changes

| File | Change | Before and after |
| --- | --- | --- |
| `backend/app/book_refresh.py` | Added coordinator with age check, concurrency bound, expiring attempt lease, overall deadline and stale fallback. | Old snapshots were returned indefinitely; eligible viewed books now attempt a guarded refresh. |
| `backend/app/sources/edition.py` | Added exact-ISBN provider reads, safe edition redirect handling and conservative edition normalization. | There was no saved-edition lookup; details can now revalidate their own ISBN/language without changing search retrieval. |
| `backend/app/repository.py` | Added conditional `refresh_book`; existing validation, search-save and read methods remain unchanged. | Metadata writes required a completed search; an existing saved book can now refresh without writing search history or overwriting a concurrent newer snapshot. |
| `backend/app/main.py` | Wired the coordinator to existing application-owned resources. | No refresh coordinator existed; the normal lifespan now provides it without adding a worker or external service. |
| `backend/app/api/books.py` | Added an optional coordinator invocation after a valid stored read. | The endpoint always returned stored data; it can now return a newly verified snapshot while preserving its response shape and initial errors. |
| `backend/tests/test_book_refresh.py` | Added 28 focused offline test cases. | Age, lease, cancellation, timeout, exact-edition and redirect behavior were untested; these boundaries now have deterministic checks. |
| `backend/integration_tests/test_book_refresh.py` | Added 14 native storage/cache test cases. | There was no isolated refresh verification; native tests now prove existing-only updates, metadata/history protection and cross-worker attempt coordination. |
| `backend/scripts/check_book_refresh.py` | Added a local-only reproducible live diagnostic with cleanup, source hashes and safe report output. | Real refresh behavior could not be independently exercised without aging normal data; disposable copies now verify it. |
| `backend/evals/results/catalog-refresh-20261109-round15.json` | Added the initial completed live capture. | Preserves real cache-miss provider reads and isolated storage results before the diagnostic lint annotation. |
| `backend/evals/results/catalog-refresh-20261109-round15-final.json` | Added the final capture matching the final diagnostic source hash. | Records the repeated catalog-cache conditions explicitly rather than overwriting the first capture. |
| `README.md` | Updated detail/cache behavior, documented limits and the diagnostic command, and removed the completed refresh item from remaining work. | Documentation promised stored-only reads and listed refresh as future work; it now describes actual lazy refresh behavior. |
| `update_version/Lumen_Update_Version_15.md` | Added this round's record. | Scope, verification, impacts and the proposed submission are now reviewable. |

No files were deleted. No frontend implementation, package, lockfile, environment setting, migration, recommendation prompt, query-retrieval function, ranking rule, spending policy or public API shape changed.

## 5. Project benefits

- Saved book pages can improve old catalog data without forcing a new recommendation or spending model requests.
- Strict edition and language checks prevent replacing a saved ISBN with another edition selected by an aggregated work response.
- Provider or coordination outages preserve a usable page and honest snapshot age.
- Timestamp comparison prevents delayed refresh work from erasing a newer save.
- Disposable verification reproduces old data and actual refresh without aging or rewriting the user's normal books or search history.

## 6. Future impact

- **Compatibility:** existing detail responses, SSE events, search requests, database schema and historical recommendations remain compatible. No client update or migration is required.
- **Resources/quotas:** stale accesses add bounded requests to the existing catalog providers. Catalog quotas still apply. The coordinator adds expiring ISBN-only Redis keys and uses existing shared resources; no new recurring service was configured.
- **Model usage:** no model is called by refresh. The approved daily 100-attempt limit and all IP/search protections remain unchanged.
- **Cache signature:** the existing broad backend-source signature changes when these modules are added. Old parse/completed-result entries become version misses without being deleted; later uncached searches may use model attempts within the existing cap. Raw catalog cache keys retain their existing independent behavior. No invalidation policy or usage counter was changed.
- **Freshness limits:** only viewed old books are refreshed. A failed attempt preserves the old timestamp and waits for lease expiry before retrying. Exact edition metadata can be absent, incomplete or unavailable. Per-field age, proactive sweeps and full provider-payload storage remain outside this round.
- **Production:** no deployment or public service was created. Proxy verification, durable usage accounting across Redis loss, CI and remaining deployment preparation are still separate work.

## 7. Verification

| Check | Actual result |
| --- | --- |
| Full offline backend suite, final run | **360 passed in 3.38 seconds**, including 28 new refresh cases. |
| Native PostgreSQL/Redis suite, final run | **45 passed in 8.56 seconds**, including 14 new cases; isolated disposable data only. |
| Frontend native regression tests | **11 passed**; existing nonfatal Node module-type warnings remain. |
| Ruff lint and format check | Passed; all **95 Python files** passed formatting verification. A diagnostic broad-exception lint finding was resolved with an explicit justification for retaining sanitized failed-check evidence. Both initial and final live reports were preserved. |
| Initial actual ISBN investigation | Google Books matched Spanish `9788417346201` and English `9780141439518`; an actual Open Library 302 exposed the edition redirect requirement, which was implemented and tested. |
| Initial isolated live refresh | **Passed** for Spanish `9788417346201`, En el mar, and English `9780330483292`, The Sea. Each had zero catalog-cache hits and a real successful Google Books response. Aged copies updated through the real API/repository boundary; public originals stayed unchanged. |
| Final isolated live refresh | **Passed** for both ISBNs, with **one existing catalog-cache hit per book**. Their stored times remained the actual initial source-fetch times. All six recorded LF-normalized source/driver hashes match final code. This retry is not claimed to be cold. |
| Live fallback probe | **Passed**: Open Library returned the same English `9780141439518`, Pride and Prejudice, using its real ISBN/edition path. Google failure was explicitly simulated for this probe; it is not evidence of an actual Google outage. No database write was made by that supplementary probe. |
| Storage/privacy/usage assertions | Both captures verified API/SQL agreement, no second-read provider work, no public snapshot mutation, no search-history additions and no private response fields. Shared model usage remained **61/100** before and after. |
| Cleanup and normal preview | Zero remaining `lumen:test:*` fixture keys and zero temporary test schemas. The normal backend was restarted with this implementation. Proxied health, both home locales and both checked book pages returned 200. |

The initial live capture ran at 13:08:06–13:08:08 UTC; the final matching capture ran at 13:08:46–13:08:47 UTC on 2026-11-09. Both use a local disposable schema and expiring test namespace; only copies are aged by 31 days. The public rows were independently read before/after and never changed by the diagnostic. Source response events identify provider paths/statuses without recording credential headers.

The existing recommendation-query retrieval, graph, prompts, ranking, stream logic, cache validation and usage guards are unchanged. A Git comparison verified their file scope; an AST comparison verified that `validate_completed`, `save_completed`, `get_book` and `_details` retain their existing logic. The 20-query AI recommendation gate was **not rerun for this saved-detail-only change**: it does not modify recommendation retrieval or prompts, and its targeted catalog-refresh gate is separately recorded. The prior completed recommendation gate is preserved and is not relabeled as new verification.

No new frontend build or visual sweep was required because frontend code/configuration did not change; the already-built preview's HTTP behavior and native frontend tests were checked. No production/load test, scheduled sweep, full catalog-coverage proof, author authority lookup or public deployment was performed. Failures deliberately injected in offline/native tests are not described as real-provider outages. Final changed-file language, whitespace, credential and attribution review is part of this round's completion checks.

## 8. Approvals and remaining work

The user explicitly authorized the Update 14 upload/main merge and starting the next task. The saved-book refresh follows the already approved specification, existing providers and database schema. The bounded lazy approach was described in conversation before implementation. No major architecture, paid-service, provider-replacement, core capability, schema, privacy or spending decision was introduced. No new approval was required for these routine implementation choices.

This round remains local for its own upload review. Public deployment still requires explicit authorization. Remaining work includes CI, production proxy/deployment and budget durability, richer sharing metadata/status-aware pages, and the documented full-provider-payload/storage boundary. A future scheduled sweep would need its own implementation and resource review; it is not claimed complete here.

Manual inspection can use either existing local detail page. A recent book should retain its saved date; repeatedly opening a fresh book does not force an external lookup. To observe old-data refresh without waiting 30 days or altering normal data, run the documented isolated diagnostic with a new output path. It makes catalog requests but no AI calls.

## 9. GitHub submission

**Proposed commit title**

`feat: refresh stale saved-book metadata by exact ISBN`

**Proposed commit description**

Saved book details could serve catalog snapshots indefinitely despite the 30-day freshness requirement. Refresh eligible existing books on access using the same ISBN and language, preferring Google Books and accepting only an identified Open Library edition as fallback. Retain stale data and its date when sources, coordination or writes fail.

Bound optional refresh to three seconds, three slots per process and one five-minute Redis attempt lease per ISBN across workers. Validate edition redirects and source timestamps, preserve missing optional metadata and coherent ratings, protect newer concurrent saves with a conditional update and keep search history private and unchanged. No model calls, schema migrations, new providers, dependencies, recommendation-retrieval changes or spending-limit changes are introduced. Existing backend-versioned parse/result caches become normal version misses.

Validation: 360 offline backend tests, 45 native PostgreSQL/Redis checks and 11 frontend tests passed; Ruff lint/format checks passed. Actual Spanish and English catalog refresh succeeded through an isolated API/database boundary without touching public books; a genuine Open Library fallback succeeded with only Google failure simulated. Initial cache-miss and final cache-hit reports are retained, with source hashes, cleanup and unchanged 61/100 shared model usage. Existing preview routes remain healthy. No production deployment or new recommendation-quality evaluation is claimed.

See `update_version/Lumen_Update_Version_15.md` for exact files, live evidence, omitted checks, compatibility and remaining work.

**Actual status:** verified local implementation on `codex/update-15-catalog-refresh`, uncommitted and not uploaded. No Update 15 upload/main-merge authorization has been received; the previous authorization covered Update 14 only. No Update 15 push, pull request, main merge, release or public deployment has occurred.
