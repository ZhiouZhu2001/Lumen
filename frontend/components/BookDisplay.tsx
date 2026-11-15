import Image from "next/image";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { ChevronIcon } from "@/components/Icons";
import type { BookMetadata, Language } from "@/lib/types";

// Catalog presentation is shared; recommendation reasons never enter saved details.
export default function BookDisplay({book, heading = "h3", children, action, rank, language}: {
  book: BookMetadata; heading?: "h1" | "h3"; children?: ReactNode; action?: ReactNode;
  rank?: number; language?: Language;
}) {
  const t = useTranslations("BookCard");
  const detailLabels = useTranslations("BookDetails");
  const Heading = heading;
  const detail = heading === "h1";
  const formatLabels: Record<string, string> = {
    paper: t("paper"), kindle: "Kindle", ebook: t("ebook"), apple_books: "Apple Books",
  };

  return (
    <article className={`book-display ${detail ? "book-detail" : ""}`}>
      {rank !== undefined ? <span className="book-rank" aria-hidden="true">{String(rank).padStart(2, "0")}</span> : null}
      <div className="book-cover">
        {book.cover_url ? <Image src={book.cover_url} alt={t("coverAlt", {title: book.title})} width={detail ? 352 : 172} height={detail ? 496 : 240} sizes={detail ? "(max-width: 672px) 104px, 352px" : "(max-width: 672px) 84px, 172px"} /> : <div className="missing-cover">{t("noCover")}</div>}
      </div>
      <div className="book-body">
        <Heading className="book-title">{book.title}</Heading>
        {book.authors.length > 0 ? <p className="book-authors">{book.authors.join(", ")}</p> : null}
        <div className="book-metadata">
          {book.published_year ? <span>{book.published_year}</span> : null}
          {book.page_count ? <span>{t("pages", {count: book.page_count})}</span> : null}
          {language ? <span>{detailLabels(language === "en" ? "english" : "spanish")}</span> : null}
        </div>
        <div className="book-supplement">
          <div className="book-formats">{book.formats.map(format => <span key={format}>{formatLabels[format] ?? format}</span>)}</div>
          <p className="book-rating">{book.rating ? <>{book.rating.value}/5 <span>({t("ratings", {count: book.rating.count})} · {book.rating.source})</span></> : t("noRating")}</p>
        </div>
        {children}
        <div className="book-links">
          {book.description ? <details className="catalog-description">
            <summary>{t("description")}<ChevronIcon /></summary>
            <p>{book.description}</p>
          </details> : null}
          {detail && book.links.length > 0 ? <h2 className="where-heading">{t("where")}</h2> : null}
          <div className="store-links">
            {book.links.map(link => <a key={link.store} href={link.url} target="_blank" rel="noopener noreferrer" className="store-link">{link.label}</a>)}
            {action}
          </div>
        </div>
        <p className="channel-note">{t("channelNote")}</p>
      </div>
    </article>
  );
}
