import test from "node:test";
import assert from "node:assert/strict";
import { bookPath, fetchBookDetails } from "../lib/book-details.ts";

const isbn = "9788417346201";
const snapshot = {
  isbn13: isbn, title: "En el mar", authors: ["Toine Heijmans"],
  language: "es", genres: [], source: "google_books",
  fetched_at: "2026-11-08T10:00:00Z", published_year: 2018,
  page_count: 128, description: null, cover_url: null, rating: null,
  formats: ["paper"], links: [{store: "amazon", label: "Amazon.es", url: "https://www.amazon.es/s?k=9788417346201", formats: ["paper"]}],
};

test("invalid or checksum-corrupted book links do not contact the backend", async () => {
  for (const value of ["bad", "9788417346202", "../api/search", "9788417346201?query=private"]) {
    const result = await fetchBookDetails(value, "http://127.0.0.1:8001", () => {throw new Error("must not fetch");});
    assert.deepEqual(result, {status: "invalid"});
  }
});

test("details read only the requested stored book and request a fresh bounded snapshot", async () => {
  let calls = 0;
  const result = await fetchBookDetails(isbn, "http://127.0.0.1:8001", async (url, options) => {
    calls++;
    assert.equal(url.href, `http://127.0.0.1:8001/api/books/${isbn}`);
    assert.equal(options.cache, "no-store");
    assert.equal(options.signal.aborted, false);
    return Response.json(snapshot);
  });
  assert.equal(calls, 1);
  assert.deepEqual(result, {status: "found", book: snapshot});
});

test("missing books, invalid links and outages keep distinct safe states", async () => {
  for (const [code, status] of [[404, "notFound"], [422, "invalid"], [503, "unavailable"], [500, "unavailable"]]) {
    assert.deepEqual(await fetchBookDetails(isbn, "http://localhost:8001", async () => Response.json({detail: "private internal URL"}, {status: code})), {status});
  }
  assert.deepEqual(await fetchBookDetails(isbn, "http://localhost:8001", async () => {throw new DOMException("private timeout", "TimeoutError");}), {status: "unavailable"});
});

test("wrong identity and malformed stored responses never render a misleading detail page", async () => {
  const invalid = [
    {...snapshot, isbn13: "9788490651261"}, {...snapshot, authors: null},
    {...snapshot, fetched_at: "bad date"}, {...snapshot, links: [null]},
    {...snapshot, rating: {value: "bad", count: 5, source: "catalog"}},
    {...snapshot, page_count: -1}, {...snapshot, links: [{...snapshot.links[0], url: "javascript:alert(1)"}]},
  ];
  for (const value of invalid) {
    assert.deepEqual(await fetchBookDetails(isbn, "http://localhost:8001", async () => Response.json(value)), {status: "unavailable"});
  }
  assert.deepEqual(await fetchBookDetails(isbn, "http://localhost:8001", async () => new Response("not JSON")), {status: "unavailable"});
});

test("localized book share paths contain only the book identity", () => {
  for (const locale of ["en", "es"]) {
    const url = new URL(bookPath(locale, isbn), new URL("https://lumen.example/es?query=private#reason").origin);
    assert.equal(url.href, `https://lumen.example/${locale}/books/${isbn}`);
    assert.equal(url.search, "");
    assert.equal(url.hash, "");
  }
});
