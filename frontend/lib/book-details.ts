import type { BookDetails, Language } from "./types.ts";
import { isBookMetadata, isIsbn13, isRecord, strings } from "./book-schema.ts";

export { isIsbn13 } from "./book-schema.ts";

export type BookDetailsResult =
  | {status: "found"; book: BookDetails}
  | {status: "invalid" | "notFound" | "unavailable"};

export function bookPath(locale: Language, isbn13: string): string {
  return `/${locale}/books/${isbn13}`;
}

function isBookDetails(value: unknown, isbn13: string): value is BookDetails {
  if (!isRecord(value) || !isBookMetadata(value)) return false;
  return value.isbn13 === isbn13 && strings(value.genres)
    && (value.language === "en" || value.language === "es") && typeof value.source === "string"
    && typeof value.fetched_at === "string" && Number.isFinite(Date.parse(value.fetched_at));
}

// Used by the server page; the public browser never needs the backend address.
export async function fetchBookDetails(isbn13: string, backendUrl: string, fetcher: typeof fetch = fetch): Promise<BookDetailsResult> {
  if (!isIsbn13(isbn13)) return {status: "invalid"};
  try {
    const response = await fetcher(new URL(`/api/books/${isbn13}`, backendUrl), {
      cache: "no-store", signal: AbortSignal.timeout(5_000),
    });
    if (response.status === 404) return {status: "notFound"};
    if (response.status === 422) return {status: "invalid"};
    if (!response.ok) return {status: "unavailable"};
    const book: unknown = await response.json();
    return isBookDetails(book, isbn13) ? {status: "found", book} : {status: "unavailable"};
  } catch {
    return {status: "unavailable"};
  }
}
