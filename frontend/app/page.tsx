"use client";

import { useState, type FormEvent } from "react";

import BookCard from "@/components/BookCard";
import type { Book } from "@/lib/types";

export default function Home() {
  const [query, setQuery] = useState("");
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>){
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, language: "es" }),
      });
      if (!response.ok) {
        throw new Error(`Search failed (${response.status})`);
      }
      const data: {books : Book[] } = await response.json();
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
      <h1 className="text-3xl font-semibold">Lumen</h1>
      <p className="mt-2 text-zinc-600">Find your next book</p>

      <form onSubmit={handleSubmit} className="mt-6 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="realismo mágico"
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
          {loading ? "Searching..." : "Search"}
        </button>
      </form>
       
       {error && <p className="mt-4 text-red-600">{error}</p>}

      <ul className="mt-6 space-y-2">
        {books.map((book) => (
          <BookCard key={book.isbn13} book={book}/>
        ))}
      </ul>
    </main>
  );
}