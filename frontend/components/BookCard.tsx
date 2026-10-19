import Image from "next/image";

import type { Book } from "@/lib/types";

export default function BookCard({ book }: { book: Book }) {
  return (
    <article className="flex gap-4 rounded-lg border border-zinc-200 p-4">
      {book.cover_url ? (
        <Image
          src={book.cover_url}
          alt={`Cover of ${book.title}`}
          width={80}
          height={120}
          className="h-[120px] w-[80px] shrink-0 rounded object-cover"
        />
      ) : (
        <div className="flex h-[120px] w-[80px] shrink-0 items-center justify-center rounded bg-zinc-100 text-xs text-zinc-400">
          No cover
        </div>
      )}

      <div className="min-w-0">
        <h2 className="font-semibold">{book.title}</h2>
        {book.authors.length > 0 && (
          <p className="text-sm text-zinc-600">{book.authors.join(", ")}</p>
        )}
        {book.published_year && (
          <p className="text-sm text-zinc-500">{book.published_year}</p>
        )}
        <p className="mt-2 text-sm">
          {book.rating ? (
            <>
              ★ {book.rating.value}{" "}
              <span className="text-zinc-500">
                ({book.rating.count} ratings · {book.rating.source})
              </span>
            </>
          ) : (
            <span className="text-zinc-400">No rating yet</span>
          )}
        </p>
      </div>
    </article>
  );
}