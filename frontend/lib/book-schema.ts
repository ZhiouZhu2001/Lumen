import type { BookMetadata } from "./types.ts";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string");
}

export function isIsbn13(value: string): boolean {
  if (!/^97[89][0-9]{10}$/.test(value)) return false;
  return [...value].reduce((sum, digit, index) => sum + Number(digit) * (index % 2 ? 3 : 1), 0) % 10 === 0;
}

// Both public book surfaces validate the same metadata before rendering it.
export function isBookMetadata(value: unknown): value is BookMetadata & Record<string, unknown> {
  return isRecord(value) && typeof value.isbn13 === "string" && isIsbn13(value.isbn13)
    && typeof value.title === "string" && value.title.trim().length > 0 && strings(value.authors)
    && strings(value.formats) && (value.description === null || typeof value.description === "string")
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
