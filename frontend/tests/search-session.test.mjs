import test from "node:test";
import assert from "node:assert/strict";
import { createSearchSession } from "../stores/search-store.ts";

const isbns = ["9788417346201", "9788490651261", "9780061120084", "9780141439518", "9780307389732"];
const books = isbns.map((isbn13, index) => ({
  isbn13, title: `Catalog fixture ${index + 1}`, authors: ["Catalog author"], rank: index + 1,
  reason: "A reason based on this catalog fixture.", published_year: 2018, page_count: 128,
  description: null, cover_url: null, rating: null, formats: ["paper"],
  links: [{store: "amazon", label: "Amazon.es", url: `https://www.amazon.es/s?k=${isbn13}`, formats: ["paper"]}],
}));
const frame = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
const done = (total, limited = total > 0 && total < 5) => frame("done", {search_id: "fixture-search", total, limited});
const response = body => new Response(body, {headers: {"Content-Type": "text/event-stream"}});
const complete = selected => response(selected.map(book => frame("book", book)).join("") + done(selected.length));
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() {
  let resolve;
  const promise = new Promise(done => {resolve = done;});
  return {promise, resolve};
}

test("sessions keep form state separate and send only selected filters", async () => {
  let request;
  const session = createSearchSession(async (url, options) => {
    request = {url, ...options};
    return complete(books);
  });
  const other = createSearchSession();
  session.store.getState().setQuery("A private reading request");
  session.store.getState().setFilter("length", "short");
  assert.equal(other.store.getState().query, "");
  assert.equal(other.store.getState().filters.length, "");
  await session.submit("es");
  assert.equal(request.url, "/api/search");
  assert.equal(request.headers.Accept, "text/event-stream");
  assert.equal(request.cache, "no-store");
  assert.deepEqual(JSON.parse(request.body), {query: "A private reading request", language: "es", filters: {length: "short"}});
  assert.equal(session.store.getState().status, "complete");
  assert.equal(session.store.getState().limited, false);
  assert.deepEqual(session.store.getState().books, books);
});

test("a superseded request cannot replace the newer result even if it ignores abort", async () => {
  const first = deferred(), second = deferred();
  const signals = [];
  const session = createSearchSession(async (_, options) => {
    signals.push(options.signal);
    return signals.length === 1 ? first.promise : second.promise;
  });
  const oldRequest = session.submit("en");
  const newRequest = session.submit("es");
  assert.equal(signals[0].aborted, true);
  second.resolve(complete([{...books[1], rank: 1}]));
  await newRequest;
  first.resolve(complete([books[0]]));
  await oldRequest;
  assert.equal(session.store.getState().status, "complete");
  assert.equal(session.store.getState().books[0].isbn13, books[1].isbn13);
});

test("cancel clears provisional cards and ignores late completion while retaining the form", async () => {
  let writer, signal;
  const stream = new ReadableStream({start(controller) {writer = controller;}});
  const session = createSearchSession(async (_, options) => {signal = options.signal; return response(stream);});
  session.store.getState().setQuery("Keep this request");
  session.store.getState().setFilter("era", "2010s");
  const running = session.submit("en");
  writer.enqueue(new TextEncoder().encode(frame("book", books[0])));
  await tick();
  assert.equal(session.store.getState().books.length, 1);
  assert.equal(session.store.getState().status, "loading");
  session.cancel();
  assert.equal(signal.aborted, true);
  writer.enqueue(new TextEncoder().encode(done(1)));
  writer.close();
  await running;
  const state = session.store.getState();
  assert.equal(state.status, "cancelled");
  assert.equal(state.query, "Keep this request");
  assert.equal(state.filters.era, "2010s");
  assert.deepEqual(state.books, []);
  assert.equal(state.error, null);
});

test("reset aborts the request and stale HTTP errors cannot overwrite idle state", async () => {
  const pending = deferred();
  const session = createSearchSession(() => pending.promise);
  const running = session.submit("en");
  session.reset();
  pending.resolve(new Response("", {status: 429}));
  await running;
  assert.equal(session.store.getState().status, "idle");
  assert.equal(session.store.getState().error, null);
});

test("hourly, daily, empty and unknown errors select safe message keys", async () => {
  for (const [makeResponse, expected] of [
    [() => new Response("", {status: 429}), "rateLimited"],
    [() => Response.json({detail: {code: "rate_limited"}}, {status: 503}), "dailyLimit"],
    [() => response(frame("error", {code: "no_results", message: "private"}) + done(0)), "noResults"],
    [() => response(frame("error", {code: "internal", message: "private"}) + done(0)), "searchFailed"],
  ]) {
    const session = createSearchSession(makeResponse);
    await session.submit("en");
    assert.equal(session.store.getState().status, "error");
    assert.equal(session.store.getState().error, expected);
    assert.deepEqual(session.store.getState().books, []);
  }
});

test("limited results use the terminal flag and repeated book frames do not duplicate cards", async () => {
  const session = createSearchSession(() => response(
    frame("future_extension", {}) + frame("status", {stage: "ranking"})
    + frame("candidates", {count: 12}) + frame("book", books[0]) + frame("book", books[0]) + done(1),
  ));
  await session.submit("en");
  assert.equal(session.store.getState().status, "complete");
  assert.equal(session.store.getState().limited, true);
  assert.equal(session.store.getState().count, 12);
  assert.deepEqual(session.store.getState().books, [books[0]]);
});

test("malformed, incomplete, inconsistent and post-terminal streams discard provisional results", async () => {
  for (const body of [
    frame("book", {...books[0], authors: null}) + done(1),
    frame("book", {...books[0], isbn13: "9788417346202"}) + done(1),
    frame("book", {...books[0], links: [{...books[0].links[0], url: "javascript:alert(1)"}]}) + done(1),
    frame("book", {...books[0], rank: 2}) + done(1),
    frame("book", books[0]),
    frame("book", books[0]) + done(2),
    frame("book", books[0]) + done(1, false),
    frame("book", books[0]) + done(1) + frame("status", {stage: "ranking"}),
    frame("status", {stage: "invalid"}) + done(0),
    frame("status", {stage: ["ranking"]}) + done(0),
    frame("book", books[0]) + frame("error", {code: "llm_failed"}) + done(1, false),
  ]) {
    const session = createSearchSession(() => response(body));
    await session.submit("en");
    assert.equal(session.store.getState().status, "error");
    assert.equal(session.store.getState().error, "searchFailed");
    assert.deepEqual(session.store.getState().books, []);
  }
});
