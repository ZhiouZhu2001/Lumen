"use client";

import { useEffect, useRef, useState, type SubmitEvent } from "react";
import { useLocale, useTranslations } from "next-intl";

import BookCard from "@/components/BookCard";
import { usePathname, useRouter } from "@/i18n/navigation";
import type { Book, Language } from "@/lib/types";
import { readSearchEvents } from "@/lib/sse";
import { searchFailureKey } from "@/lib/search-error";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "es", label: "Español" },
  { code: "en", label: "English" },
];

export default function Home() {
  // The language now lives in the URL: /es or /en
  const language = useLocale();
  const t = useTranslations("HomePage");
  const router = useRouter();
  const pathname = usePathname();

  const [query, setQuery] = useState("");
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stage, setStage] = useState("");
  const [count, setCount] = useState<number | null>(null);
  const [genre, setGenre] = useState("");
  const [era, setEra] = useState("");
  const [length, setLength] = useState("");
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => active.current?.abort(), []);

  function changeLanguage(next: Language) {
    active.current?.abort();
    active.current = null;
    setLoading(false);
    setBooks([]);
    setError(null);
    setStage("");
    setCount(null);
    // Same page, other language: /es → /en
    router.replace(pathname, { locale: next });
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault(); // stop the browser from reloading the page
    setLoading(true);
    setError(null);
    setBooks([]);
    setStage("parsing");
    setCount(null);
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    try {
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        signal: controller.signal,
        body: JSON.stringify({ query, language, filters: {
          ...(genre ? {genre} : {}), ...(era ? {era} : {}), ...(length ? {length} : {}),
        } }),
      });
      if (!response.ok) {
        const key = await searchFailureKey(response);
        if (active.current === controller) setError(t(key));
        return;
      }
      await readSearchEvents(response, ({event, data}) => {
        if (active.current !== controller || !data || typeof data !== "object") return;
        if (event === "status" && "stage" in data) setStage(String(data.stage));
        if (event === "candidates" && "count" in data) setCount(Number(data.count));
        if (event === "book" && "isbn13" in data) {
          const book = data as Book;
          setBooks(previous => previous.some(b => b.isbn13 === book.isbn13) ? previous : [...previous, book]);
        }
        if (event === "error" && "code" in data) {
          setError(t(data.code === "no_results" ? "noResults" : data.code === "rate_limited" ? "dailyLimit" : "searchFailed"));
        }
        if (event === "done") setStage("done");
      });
    } catch {
      if (!controller.signal.aborted && active.current === controller) setError(t("searchFailed"));
    } finally {
      if (active.current === controller) setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Lumen</h1>
          <p className="mt-2 text-zinc-600">{t("tagline")}</p>
        </div>

        <div className="flex overflow-hidden rounded border border-zinc-300 text-sm">
          {LANGUAGES.map(({ code, label }) => (
            <button
              key={code}
              type="button"
              onClick={() => changeLanguage(code)}
              aria-pressed={language === code}
              className={
                language === code
                  ? "min-h-11 bg-black px-3 py-1 text-white"
                  : "min-h-11 px-3 py-1 text-zinc-600 hover:bg-zinc-100"
              }
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label htmlFor="query" className="block text-sm font-medium">{t("requestLabel")}</label>
        <div className="flex gap-2">
        <input
          id="query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("placeholder")}
          minLength={3}
          maxLength={300}
          required
          className="min-w-0 flex-1 rounded border border-zinc-300 px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading}
          className="min-h-11 rounded bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? t("searchingButton") : t("search")}
        </button>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm">{t("genre")}
            <select value={genre} onChange={e => setGenre(e.target.value)} disabled={loading} className="mt-1 block min-h-11 w-full rounded border border-zinc-300 bg-white px-2">
              <option value="">{t("any")}</option>
              <option value="historical fiction">{t("historical")}</option>
              <option value="graphic novels">{t("comics")}</option>
              <option value="manga">Manga</option>
              <option value="fantasy">{t("fantasy")}</option>
              <option value="thriller">Thriller</option>
            </select>
          </label>
          <label className="text-sm">{t("era")}
            <select value={era} onChange={e => setEra(e.target.value)} disabled={loading} className="mt-1 block min-h-11 w-full rounded border border-zinc-300 bg-white px-2">
              <option value="">{t("any")}</option>
              {["2020s", "2010s", "2000s", "1990s", "1980s"].map(value => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label className="text-sm">{t("length")}
            <select value={length} onChange={e => setLength(e.target.value)} disabled={loading} className="mt-1 block min-h-11 w-full rounded border border-zinc-300 bg-white px-2">
              <option value="">{t("any")}</option>
              <option value="short">{t("short")}</option>
              <option value="medium">{t("medium")}</option>
              <option value="long">{t("long")}</option>
            </select>
          </label>
        </div>
        <p className="text-xs text-zinc-600">{t("filterNote")}</p>
      </form>

      <div role="status" aria-live="polite" className="mt-4 text-sm text-zinc-600">
        {loading ? t(stage === "parsing" ? "parsing" : stage === "ranking" ? "ranking" : "searching") : stage === "done" && !error ? t(books.length > 0 && books.length < 5 ? "limited" : "complete", {count: books.length}) : ""}
        {loading && count !== null ? ` · ${t("candidates", {count})}` : ""}
      </div>
      {error && <p role="alert" className="mt-4 text-red-600">{error}</p>}

      <div aria-busy={loading} className="mt-6 space-y-4">
        {books.map((book) => (
          <BookCard key={book.isbn13} book={book} detailsAvailable={stage === "done" && !error} />
        ))}
      </div>
    </main>
  );
}
