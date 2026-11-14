import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { createBookMetadata } from "../lib/book-metadata.ts";

const book = {
  isbn13: "9788417346201", title: "En el mar", authors: ["Toine Heijmans"], language: "es",
  genres: [], source: "google_books", fetched_at: "2026-11-08T10:00:00Z",
  published_year: 2018, page_count: 128, description: "private search and recommendation data",
  cover_url: "https://covers.openlibrary.org/b/isbn/9788417346201-L.jpg", rating: null,
  formats: ["paper"], links: [],
};

function copy(locale) {
  const messages = JSON.parse(readFileSync(new URL(`../messages/${locale}.json`, import.meta.url), "utf8")).BookDetails;
  const format = (template, values) => template.replace(/\{(\w+)\}/g, (_, key) => values[key]);
  return {
    unavailableTitle: messages.errorTitle,
    statuses: {invalid: messages.invalid, notFound: messages.notFound, unavailable: messages.unavailable},
    describe: (title, authors, isbn) => format(authors ? messages.previewDescriptionWithAuthors : messages.previewDescriptionWithoutAuthors, {title, authors, isbn}),
    coverAlt: title => format(messages.previewCoverAlt, {title}),
  };
}

for (const locale of ["en", "es"]) {
  test(`${locale} previews identify the actual book with localized public copy`, () => {
    const result = createBookMetadata({status: "found", book}, copy(locale));
    assert.equal(result.title, "En el mar | Lumen");
    assert.match(result.description, /Toine Heijmans/);
    assert.match(result.description, /9788417346201/);
    assert.ok(result.description.startsWith(locale === "en" ? "Details for " : "Detalles de "));
    assert.equal(result.openGraph.title, result.title);
    assert.equal(result.twitter.description, result.description);
    assert.equal(result.twitter.card, "summary_large_image");
    assert.equal(result.openGraph.images[0].url, book.cover_url);
    assert.equal(result.openGraph.images[0].alt, `${locale === "en" ? "Cover of" : "Portada de"} En el mar`);
    assert.equal(result.robots, undefined);
    assert.equal(result.metadataBase, undefined);
    assert.equal(result.alternates, undefined);
    assert.equal(result.openGraph.url, undefined);
  });

  for (const status of ["invalid", "notFound", "unavailable"]) {
    test(`${locale} ${status} links have safe localized noindex previews`, () => {
      const labels = copy(locale);
      const result = createBookMetadata({status}, labels);
      assert.equal(result.title, `${labels.unavailableTitle} | Lumen`);
      assert.equal(result.description, labels.statuses[status]);
      assert.deepEqual(result.robots, {index: false, follow: false});
      assert.deepEqual(result.openGraph.images, []);
      assert.deepEqual(result.twitter.images, []);
      assert.equal(result.twitter.card, "summary");
    });
  }

  test(`${locale} unknown authors and absent covers do not invent bibliography or images`, () => {
    const result = createBookMetadata({status: "found", book: {...book, authors: [], cover_url: null}}, copy(locale));
    assert.ok(result.description.startsWith(locale === "en" ? "Details for En el mar. ISBN" : "Detalles de En el mar. ISBN"));
    assert.deepEqual(result.openGraph.images, []);
    assert.equal(result.twitter.card, "summary");
    assert.doesNotMatch(JSON.stringify(result), /unknown author|autor desconocido/i);
  });
}

test("metadata omits descriptions, search state, reasons and request origins", () => {
  const original = structuredClone(book);
  const result = createBookMetadata({status: "found", book, query: "private_reader_query", reason: "private_recommendation"}, copy("en"));
  assert.doesNotMatch(JSON.stringify(result), /private|127\.0\.0\.1|localhost|lumen\.example/);
  assert.deepEqual(book, original);
});

test("public titles and authors become bounded plain text without splitting Unicode", () => {
  let result = createBookMetadata({status: "found", book: {...book, title: "<b>En</b>\u0000 el\nmar", authors: ["<i>Toine</i> Heijmans"]}}, copy("en"));
  assert.equal(result.title, "En el mar | Lumen");
  assert.match(result.description, /Toine Heijmans/);
  assert.doesNotMatch(JSON.stringify(result), /<b>|<i>|\\u0000/);
  result = createBookMetadata({status: "found", book: {...book, title: "📚".repeat(190)}}, copy("en"));
  assert.equal(result.title, `${"📚".repeat(180)} | Lumen`);
  assert.ok(Array.from(result.description).length <= 320);
});

test("an empty visible catalog title uses unavailable metadata instead of an invented title", () => {
  const result = createBookMetadata({status: "found", book: {...book, title: "<b></b>"}}, copy("en"));
  assert.deepEqual(result.robots, {index: false, follow: false});
  assert.equal(result.title, "Book details unavailable | Lumen");
});

for (const cover of [
  "not a URL", "javascript:alert(1)", "http://books.google.com/books/content?id=real",
  "https://unreviewed.example/cover.jpg", "https://covers.openlibrary.org:444/cover.jpg",
  "https://user:private@books.google.com/cover.jpg", "https://books.google.com/cover.jpg#private",
  "https://books.google.com/cover.jpg?key=private", "https://books.google.com/cover.jpg?TOKEN=private",
  "https://books.google.com/cover.jpg?query=private", "https://books.google.com/cover.jpg?reason=private",
]) {
  test(`unusable or credential-bearing cover is omitted: ${cover.split("?")[0]}`, () => {
    const result = createBookMetadata({status: "found", book: {...book, cover_url: cover}}, copy("en"));
    assert.deepEqual(result.openGraph.images, []);
    assert.deepEqual(result.twitter.images, []);
    assert.equal(result.twitter.card, "summary");
    assert.doesNotMatch(JSON.stringify(result), /private|unreviewed/);
  });
}

test("the existing Google Books cover shape remains usable", () => {
  const cover = "https://books.google.com/books/content?id=real-catalog-id&printsec=frontcover&img=1&zoom=1&source=gbs_api";
  const result = createBookMetadata({status: "found", book: {...book, cover_url: cover}}, copy("en"));
  assert.equal(result.openGraph.images[0].url, cover);
});
