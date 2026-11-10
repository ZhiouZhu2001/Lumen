import Image from "next/image";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import type { BookMetadata } from "@/lib/types";

// Shared catalog presentation keeps saved details and streamed cards consistent.
export default function BookDisplay({book, heading = "h2", children}: {
  book: BookMetadata; heading?: "h1" | "h2"; children?: ReactNode;
}) {
  const t = useTranslations("BookCard");
  const Heading = heading;
  const formatLabels: Record<string, string> = {
    paper: t("paper"), kindle: "Kindle", ebook: t("ebook"), apple_books: "Apple Books",
  };

  return (
    <article className="flex gap-3 rounded-lg border border-zinc-200 p-4 sm:gap-4">
      {book.cover_url ? (
        <Image src={book.cover_url} alt={t("coverAlt", {title: book.title})} width={80} height={120} className="h-[96px] w-[64px] shrink-0 rounded object-cover sm:h-[120px] sm:w-[80px]" />
      ) : (
        <div className="flex h-[96px] w-[64px] shrink-0 items-center justify-center rounded bg-zinc-100 text-xs text-zinc-600 sm:h-[120px] sm:w-[80px]">{t("noCover")}</div>
      )}
      <div className="min-w-0 flex-1 break-words">
        <Heading className={heading === "h1" ? "text-2xl font-semibold" : "font-semibold"}>{book.title}</Heading>
        {book.authors.length > 0 ? <p className="text-sm text-zinc-600">{book.authors.join(", ")}</p> : null}
        {book.published_year ? <p className="text-sm text-zinc-500">{book.published_year}</p> : null}
        {book.page_count ? <p className="text-sm text-zinc-600">{t("pages", {count: book.page_count})}</p> : null}
        <div className="mt-2 flex flex-wrap gap-1">
          {book.formats.map(format => <span key={format} className="rounded bg-zinc-100 px-2 py-1 text-xs text-zinc-700">{formatLabels[format] ?? format}</span>)}
        </div>
        <p className="mt-2 text-sm">
          {book.rating ? <>
            ★ {book.rating.value}{" "}
            <span className="text-zinc-500">({t("ratings", {count: book.rating.count})} · {book.rating.source})</span>
          </> : <span className="text-zinc-600">{t("noRating")}</span>}
        </p>
        {children}
        {book.description ? <details className="mt-3 text-sm">
          <summary className="min-h-11 cursor-pointer py-3">{t("description")}</summary>
          <p className="mt-2 whitespace-pre-line break-words text-zinc-600">{book.description}</p>
        </details> : null}
        <div className="mt-3 flex flex-wrap gap-2">
          {book.links.map(link => <a key={link.store} href={link.url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 max-w-full items-center rounded border border-zinc-300 px-3 py-2 text-sm hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2">{link.label}</a>)}
        </div>
        <p className="mt-2 text-xs text-zinc-500">{t("channelNote")}</p>
      </div>
    </article>
  );
}
