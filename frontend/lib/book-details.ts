import type { BookDetails, Language } from "./types.ts";

export type BookDetailsResult =
  | {status: "found"; book: BookDetails}
  | {status: "invalid" | "notFound" | "unavailable"};

export function isIsbn13(value: string): boolean {
  if (!/^97[89][0-9]{10}$/.test(value)) return false;
  return [...value].reduce((sum, digit, index) => sum + Number(digit) * (index % 2 ? 3 : 1), 0) % 10 === 0;
}

export function bookPath(locale: Language, isbn13: string): string {
  return `/${locale}/books/${isbn13}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string");
}

function isBookDetails(value: unknown, isbn13: string): value is BookDetails {
  if (!isRecord(value)) return false;
  return value.isbn13 === isbn13 && typeof value.title === "string" && value.title.trim().length > 0
    && strings(value.authors) && strings(value.genres) && strings(value.formats)
    && (value.language === "en" || value.language === "es") && typeof value.source === "string"
    && typeof value.fetched_at === "string" && Number.isFinite(Date.parse(value.fetched_at))
    && (value.description === null || typeof value.description === "string")
    && (value.cover_url === null || typeof value.cover_url === "string")
    && (value.page_count === null || (Number.isInteger(value.page_count) && Number(value.page_count) > 0))
    && (value.published_year === null || Number.isInteger(value.published_year))
    && (value.rating === null || (isRecord(value.rating) && typeof value.rating.value === "string"
      && Number.isFinite(Number(value.rating.value)) && Number(value.rating.value) >= 0 && Number(value.rating.value) <= 5
      && Number.isInteger(value.rating.count) && Number(value.rating.count) >= 0 && typeof value.rating.source === "string"))
    && Array.isArray(value.links) && value.links.every(link => isRecord(link)
      && typeof link.store === "string" && typeof link.label === "string"
      && typeof link.url === "string" && /^https:\/\//.test(link.url) && strings(link.formats));
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
