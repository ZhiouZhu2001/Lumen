import type { Metadata } from "next";

import type { BookDetailsResult } from "./book-details.ts";

type MissingStatus = Exclude<BookDetailsResult["status"], "found">;

export type BookPreviewCopy = {
  unavailableTitle: string;
  statuses: Record<MissingStatus, string>;
  describe: (title: string, authors: string, isbn: string) => string;
  coverAlt: (title: string) => string;
};

function plain(value: string, limit: number): string {
  const text = value.replace(/<[^>]*>/g, " ").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim();
  return Array.from(text).slice(0, limit).join("");
}

function previewCover(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || !["books.google.com", "covers.openlibrary.org"].includes(url.hostname)
      || url.username || url.password || url.port || url.hash) return null;
    const privateParameters = /^(?:key|api_key|token|access_token|q|query|search|reason)$/i;
    if ([...url.searchParams.keys()].some(key => privateParameters.test(key))) return null;
    return url.href;
  } catch {
    return null;
  }
}

// Previews use public bibliographic identity, never search text or AI reasons.
export function createBookMetadata(result: BookDetailsResult, copy: BookPreviewCopy): Metadata {
  if (result.status !== "found") {
    const title = `${copy.unavailableTitle} | Lumen`;
    const description = copy.statuses[result.status];
    return {
      title, description, robots: {index: false, follow: false},
      openGraph: {type: "website", title, description, images: []},
      twitter: {card: "summary", title, description, images: []},
    };
  }
  const book = result.book;
  const bookTitle = plain(book.title, 180);
  if (!bookTitle) return createBookMetadata({status: "unavailable"}, copy);
  const authors = plain(book.authors.map(author => plain(author, 100)).filter(Boolean).join(", "), 180);
  const title = `${bookTitle} | Lumen`;
  const description = plain(copy.describe(bookTitle, authors, book.isbn13), 320);
  const cover = previewCover(book.cover_url);
  const images = cover ? [{url: cover, alt: plain(copy.coverAlt(bookTitle), 220)}] : [];
  return {
    title, description,
    openGraph: {type: "website", title, description, images},
    twitter: {card: cover ? "summary_large_image" : "summary", title, description, images},
  };
}
