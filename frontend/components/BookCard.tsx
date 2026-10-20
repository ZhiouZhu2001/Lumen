import Image from "next/image";
import { useTranslations } from "next-intl";

import type { Book } from "@/lib/types";

export default function BookCard({ book }: { book: Book }) {
  const t = useTranslations("BookCard");

  return (
    <article className="flex gap-4 rounded-lg border border-zinc-200 p-4">
      {book.cover_url ? (
        <Image
          src={book.cover_url}
          alt={t("coverAlt", { title: book.title })}
          width={80}
          height={120}
          className="h-[120px] w-[80px] shrink-0 rounded object-cover"
        />
      ) : (
        <div className="flex h-[120px] w-[80px] shrink-0 items-center justify-center rounded bg-zinc-100 text-xs text-zinc-400">
          {t("noCover")}
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
                ({t("ratings", { count: book.rating.count })} ·{" "}
                {book.rating.source})
              </span>
            </>
          ) : (
            <span className="text-zinc-400">{t("noRating")}</span>
          )}
        </p>
      </div>
    </article>
  );
}