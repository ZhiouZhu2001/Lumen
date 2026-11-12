# Application observability

The API lifespan configures the `app` logger at INFO with one JSON handler and no propagation to a potentially unfiltered root handler. Repeated configuration reuses that handler and removes other application handlers. It does not turn on third-party HTTP or SQL debug logging. Keep `SQL_ECHO=false` in production.

Application events go to stderr, so an operator can read them through `docker compose logs backend`. No external telemetry service, new endpoint, database table or background exporter is introduced.

## Event contract

| Event | Meaning |
| --- | --- |
| `search_started` | A recommendation stream began; includes its cache-hit flag. |
| `node_finished` | One actual graph node completed, failed or was cancelled; includes that node's wall duration and model counters. |
| `model_call_finished` | One structured model invocation finished; duration includes SDK backoff/retries. |
| `model_attempt_reserved` | The existing durable budget reservation committed before an outbound HTTP attempt. |
| `search_progress` | The unchanged graph update was observed while producing SSE progress. |
| `search_finished` | A stream was exhausted, closed or interrupted; includes overall wall duration, outcome, cache status, emitted book count and counters. |
| Catalog/cache/storage/refresh warnings | A fixed event identifier and, where applicable, an allowlisted source or HTTP status replace raw exception text. |

Each record has a UTC timestamp, standard level and fixed event identifier. Search records share the same generated `search_id` as the existing SSE terminal event. Node/model events also identify one of the four fixed graph nodes. Request context is bound only while advancing or closing the iterator, never across a yielded frame. Concurrent tasks, interleaved generators and closing a generator from another task therefore restore the caller's context.

`duration_ms` on `node_finished` measures that invocation, including its awaited work. `elapsed_ms` on progress remains cumulative. Overall search duration includes waiting between streamed frames and is not a CPU measurement. A cancelled stream may have emitted provisional cards: `book_count` is not proof of database commit or browser receipt. Expected empty results finish with `outcome=completed` and `error_code=no_results`; provider, storage and budget failures remain distinguishable through their safe codes.

## Model usage is counted, not estimated

- `model_calls` counts entries into the structured model wrapper, including failed invocations. Graph progress reflects the graph state available at that update; the final trace includes an invocation that subsequently failed.
- `model_attempts` counts successfully committed pre-send reservations, including SDK retries. Denied reservations count as zero attempts. Failed sends keep their reservation count and are never refunded.
- A cache replay has zero model calls and attempts. A test model that directly returns a Pydantic result can have logical calls but zero actual transport reservations.
- These are request-local diagnostics. The PostgreSQL singleton remains the authoritative 100-attempt daily safeguard. Logs neither grant allowance nor reconcile an old ledger. Token totals and currency costs are not measured by these counters.

## Data minimization

The formatter emits only fixed events, valid UUIDs, known node/source/outcome/error identifiers, booleans and nonnegative numeric timing/count fields. Unknown messages become `application_event`. Arguments, exception tracebacks and arbitrary extras are never formatted into application JSON. Search text, prompts, responses, candidate metadata, recommendation reasons, URLs, API keys, IPs and cache keys are excluded. A broken logging sink is ignored rather than interrupting a recommendation or dumping a raw record.

This contract covers application logs. It does not redact unrelated Docker, proxy, database or third-party processes. Keep access/debug logging off unless an explicitly reviewed policy defines its data handling. Do not enable a root INFO handler for HTTP clients during production troubleshooting.

No retention or shipping policy is activated by this change. Before launch, choose bounded local log retention and whether any external collection is allowed; do not send reader data or unreviewed logs to a hosted service.

Backend code changes use the existing conservative `SearchCache` code signature. Deploying this round changes the effective parse/result namespace and can cause cold searches under the unchanged daily cap. It does not clear Redis or reset the ledger.

The implementation uses Python's [context-local state](https://docs.python.org/3.12/library/contextvars.html) and standard logging handlers. These support asynchronous isolation without adding a telemetry dependency.
