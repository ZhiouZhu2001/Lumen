import { createStore } from "zustand/vanilla";

import { decodeSearchEvent, type SearchStage } from "../lib/search-events.ts";
import { searchFailureKey, type SearchFailureKey } from "../lib/search-error.ts";
import { readSearchEvents } from "../lib/sse.ts";
import type { Book, Language } from "../lib/types.ts";

export type SearchFilters = {genre: string; era: string; length: string};
export type SearchErrorKey = SearchFailureKey | "noResults";
type SearchResults = {
  status: "idle" | "loading" | "complete" | "error" | "cancelled";
  stage: SearchStage;
  books: Book[];
  count: number | null;
  error: SearchErrorKey | null;
  limited: boolean;
};
type SearchState = SearchResults & {
  query: string;
  filters: SearchFilters;
  setQuery: (query: string) => void;
  setFilter: (name: keyof SearchFilters, value: string) => void;
};

function emptyResults(): SearchResults {
  return {status: "idle", stage: "parsing", books: [], count: null, error: null, limited: false};
}

// One session per mounted search page. Never share request state during SSR.
export function createSearchSession(fetcher: typeof fetch = fetch) {
  const store = createStore<SearchState>()(set => ({
    ...emptyResults(), query: "", filters: {genre: "", era: "", length: ""},
    setQuery: query => set({query}),
    setFilter: (name, value) => set(state => ({filters: {...state.filters, [name]: value}})),
  }));
  let active: AbortController | null = null;

  function stop(status: "idle" | "cancelled") {
    active?.abort();
    active = null;
    // Streamed cards are provisional until the successful terminal response.
    store.setState({...emptyResults(), status});
  }

  async function submit(language: Language) {
    active?.abort();
    const controller = new AbortController();
    active = controller;
    const current = () => active === controller && !controller.signal.aborted;
    const {query, filters} = store.getState();
    store.setState({...emptyResults(), status: "loading"});
    const fail = (error: SearchErrorKey) => store.setState({...emptyResults(), status: "error", error});
    let completed = false;
    try {
      const response = await fetcher("/api/search", {
        method: "POST", headers: {"Content-Type": "application/json", Accept: "text/event-stream"},
        cache: "no-store", signal: controller.signal,
        body: JSON.stringify({query, language, filters: Object.fromEntries(Object.entries(filters).filter(([, value]) => value))}),
      });
      if (!current()) return;
      if (!response.ok) {
        const key = await searchFailureKey(response);
        if (current()) fail(key);
        return;
      }
      await readSearchEvents(response, frame => {
        if (!current()) return;
        const update = decodeSearchEvent(frame);
        if (!update) return;
        if (completed) throw new Error("Search event after completion");
        const state = store.getState();
        switch (update.event) {
          case "status": store.setState({stage: update.data.stage}); break;
          case "candidates": store.setState({count: update.data.count}); break;
          case "book": {
            const book = update.data;
            const duplicate = state.books.find(previous => previous.isbn13 === book.isbn13);
            if (duplicate?.rank === book.rank) break;
            if (duplicate || book.rank !== state.books.length + 1) throw new Error("Invalid book order");
            store.setState({books: [...state.books, book]});
            break;
          }
          case "error": store.setState({error: update.data.code === "no_results" ? "noResults" : update.data.code === "rate_limited" ? "dailyLimit" : "searchFailed"}); break;
          case "done":
            if (update.data.total !== state.books.length
              || update.data.limited !== (!state.error && state.books.length > 0 && state.books.length < 5)) {
              throw new Error("Invalid search completion");
            }
            completed = true;
            store.setState({limited: update.data.limited});
        }
      });
      if (current()) {
        const state = store.getState();
        if (state.error || !state.books.length) fail(state.error ?? "noResults");
        else store.setState({status: "complete"});
      }
    } catch {
      if (current()) fail("searchFailed");
    } finally {
      if (active === controller) active = null;
    }
  }

  return {store, submit, cancel: () => stop("cancelled"), reset: () => stop("idle")};
}
