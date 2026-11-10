import { isBookMetadata, isRecord } from "./book-schema.ts";
import type { SearchEvent } from "./sse.ts";
import type { Book } from "./types.ts";

export type SearchStage = "parsing" | "searching" | "ranking";
export type SearchUpdate =
  | {event: "status"; data: {stage: SearchStage}}
  | {event: "candidates"; data: {count: number}}
  | {event: "book"; data: Book}
  | {event: "error"; data: {code: string}}
  | {event: "done"; data: {total: number; limited: boolean}};

// Unknown events are additive extensions. Malformed known events fail safely.
export function decodeSearchEvent({event, data}: SearchEvent): SearchUpdate | null {
  if (!["status", "candidates", "book", "error", "done"].includes(event)) return null;
  if (isRecord(data)) {
    if (event === "status" && (data.stage === "parsing" || data.stage === "searching" || data.stage === "ranking")) {
      return {event, data: {stage: data.stage}};
    }
    if (event === "candidates" && Number.isInteger(data.count) && Number(data.count) >= 0) {
      return {event, data: {count: Number(data.count)}};
    }
    if (event === "book" && isBookMetadata(data) && Number.isInteger(data.rank)
      && Number(data.rank) >= 1 && Number(data.rank) <= 10
      && typeof data.reason === "string" && data.reason.trim().length > 0) {
      return {event, data: data as Book};
    }
    if (event === "error" && typeof data.code === "string") return {event, data: {code: data.code}};
    if (event === "done" && Number.isInteger(data.total) && Number(data.total) >= 0
      && Number(data.total) <= 10 && typeof data.limited === "boolean") {
      return {event, data: {total: Number(data.total), limited: data.limited}};
    }
  }
  throw new Error("Invalid search event");
}
