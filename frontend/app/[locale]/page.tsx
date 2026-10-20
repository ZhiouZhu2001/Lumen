"use client";

import { useState, type SubmitEvent } from "react";
import { useLocale } from "next-intl";

import BookCard from "@/components/BookCard";
import { usePathname, useRouter } from "@/i18n/navigation";
import type { Book, Language } from "@/lib/types";

const LANGUAGES: { code: Language; label: string }[] = [
  { code: "es", label: "Español" },
  { code: "en", label: "English" },
];

const PLACEHOLDERS: Record<Language, string> = {
  es: "realismo mágico",
  en: "magical realism",
};

export default function Home() {
  // The language now lives in the URL: /es or /en
  const language = useLocale() as Language;
  const router = useRouter();
  const pathname = usePathname();

  const [query, setQuery] = useState("");
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function changeLanguage(next: Language) {
    // Same page, other language: /es → /en
    router.replace(pathname, { locale: next });
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault(); // stop the browser from reloading the page
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, language }),
      });
      if (!response.ok) {
        throw new Error(`Search failed (${response.status})`);
      }
      const data: { books: Book[] } = await response.json();
      setBooks(data.books);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
      setBooks([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Lumen</h1>
          <p className="mt-2 text-zinc-600">Find your next book.</p>
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
                  ? "bg-black px-3 py-1 text-white"
                  : "px-3 py-1 text-zinc-600 hover:bg-zinc-100"
              }
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={PLACEHOLDERS[language]}
          minLength={3}
          maxLength={300}
          required
          className="flex-1 rounded border border-zinc-300 px-3 py-2"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error && <p className="mt-4 text-red-600">{error}</p>}

      <div className="mt-6 space-y-4">
        {books.map((book) => (
          <BookCard key={book.isbn13} book={book} />
        ))}
      </div>
    </main>
  );
}