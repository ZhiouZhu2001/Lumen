import type { Metadata } from "next";
import { cache, Suspense } from "react";
import { hasLocale, useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";

import BookDisplay from "@/components/BookDisplay";
import ShareBook from "@/components/ShareBook";
import { ArrowIcon } from "@/components/Icons";
import { Masthead, SiteFooter } from "@/components/SiteChrome";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { bookPath, fetchBookDetails } from "@/lib/book-details";
import { createBookMetadata } from "@/lib/book-metadata";
import type { Language } from "@/lib/types";

type Props = PageProps<"/[locale]/books/[isbn13]">;

// The bounded fetch supplies an AbortSignal, so share its result explicitly
// between page and metadata within this request, without a persistent cache.
const getBookDetails = cache((isbn13: string) => fetchBookDetails(isbn13, process.env.BACKEND_URL ?? "http://localhost:8001"));

export async function generateMetadata({params}: Props): Promise<Metadata> {
  const {locale, isbn13} = await params;
  if (!hasLocale(routing.locales, locale)) return {robots: {index: false, follow: false}};
  const [result, t] = await Promise.all([getBookDetails(isbn13), getTranslations({locale, namespace: "BookDetails"})]);
  return createBookMetadata(result, {
    unavailableTitle: t("errorTitle"),
    statuses: {invalid: t("invalid"), notFound: t("notFound"), unavailable: t("unavailable")},
    describe: (title, authors, isbn) => t(authors ? "previewDescriptionWithAuthors" : "previewDescriptionWithoutAuthors", {title, authors, isbn}),
    coverAlt: title => t("previewCoverAlt", {title}),
  });
}

function Loading() {
  const t = useTranslations("BookDetails");
  return <main id="main-content" className="site-shell detail-message"><p role="status">{t("loading")}</p></main>;
}

async function Details({params}: Props) {
  const [{locale, isbn13}, t] = await Promise.all([params, getTranslations("BookDetails")]);
  const result = await getBookDetails(isbn13);
  const sourceLabels: Record<string, string> = {google_books: "Google Books", open_library: "Open Library"};

  return (
    <div className="site-shell">
      <Masthead>
        <nav aria-label={t("navigation")} className="locale-controls">
          {([{code: "es", label: "Español"}, {code: "en", label: "English"}] as const).map(({code, label}) => (
            <Link key={code} href={`/books/${isbn13}`} locale={code} prefetch={false} aria-current={locale === code ? "page" : undefined} className="locale-link">{label}</Link>
          ))}
        </nav>
      </Masthead>
      <main id="main-content">
      <Link href="/" className="back-link"><ArrowIcon direction="left" />{t("back")}</Link>
      {result.status === "found" ? <>
        <BookDisplay book={result.book} heading="h1" language={result.book.language} />
        <dl className="snapshot">
          <div><dt>ISBN-13</dt><dd>{result.book.isbn13}</dd></div>
          <div><dt>{t("language")}</dt><dd>{t(result.book.language === "en" ? "english" : "spanish")}</dd></div>
          <div><dt>{t("source")}</dt><dd>{sourceLabels[result.book.source] ?? t("storedCatalog")}</dd></div>
          <div><dt>{t("fetchedAt")}</dt><dd><time dateTime={result.book.fetched_at}>{new Intl.DateTimeFormat(locale, {dateStyle: "medium", timeZone: "UTC"}).format(new Date(result.book.fetched_at))}</time></dd></div>
        </dl>
        <p className="snapshot-note">{t("snapshotNote")}</p>
        <ShareBook key={`${locale}:${isbn13}`} isbn13={result.book.isbn13} />
      </> : <section className="detail-message">
        <h1>{t("errorTitle")}</h1>
        <p role="alert">{t(result.status)}</p>
        {result.status === "unavailable" ? <a href={bookPath(locale as Language, isbn13)} className="secondary-button">{t("retry")}</a> : null}
      </section>}
      </main>
      <SiteFooter />
    </div>
  );
}

export default function BookDetailsPage(props: Props) {
  return <Suspense fallback={<Loading />}><Details {...props} /></Suspense>;
}
