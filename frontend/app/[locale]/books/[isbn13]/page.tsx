import { Suspense } from "react";
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";

import BookDisplay from "@/components/BookDisplay";
import ShareBook from "@/components/ShareBook";
import { Link } from "@/i18n/navigation";
import { bookPath, fetchBookDetails } from "@/lib/book-details";
import type { Language } from "@/lib/types";

type Props = PageProps<"/[locale]/books/[isbn13]">;

function Loading() {
  const t = useTranslations("BookDetails");
  return <main className="mx-auto w-full max-w-2xl p-4 sm:p-8"><p role="status">{t("loading")}</p></main>;
}

async function Details({params}: Props) {
  const [{locale, isbn13}, t] = await Promise.all([params, getTranslations("BookDetails")]);
  const result = await fetchBookDetails(isbn13, process.env.BACKEND_URL ?? "http://localhost:8001");
  const sourceLabels: Record<string, string> = {google_books: "Google Books", open_library: "Open Library"};

  return (
    <main className="mx-auto w-full max-w-2xl p-4 sm:p-8">
      <nav aria-label={t("navigation")} className="mb-6 flex flex-wrap items-center justify-between gap-2 text-sm">
        <Link href="/" className="inline-flex min-h-11 items-center rounded underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4">{t("back")}</Link>
        <div className="flex flex-wrap gap-2">
          {([{code: "es", label: "Español"}, {code: "en", label: "English"}] as const).map(({code, label}) => (
            <Link key={code} href={`/books/${isbn13}`} locale={code} prefetch={false} aria-current={locale === code ? "page" : undefined} className={`inline-flex min-h-11 items-center rounded border px-3 py-2 ${locale === code ? "border-black bg-black text-white" : "border-zinc-300 hover:bg-zinc-100"}`}>
              {label}
            </Link>
          ))}
        </div>
      </nav>
      {result.status === "found" ? <>
        <BookDisplay book={result.book} heading="h1" />
        <dl className="mt-6 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 break-words text-sm">
          <dt className="text-zinc-600">ISBN-13</dt><dd>{result.book.isbn13}</dd>
          <dt className="text-zinc-600">{t("language")}</dt><dd>{t(result.book.language === "en" ? "english" : "spanish")}</dd>
          <dt className="text-zinc-600">{t("source")}</dt><dd>{sourceLabels[result.book.source] ?? t("storedCatalog")}</dd>
          <dt className="text-zinc-600">{t("fetchedAt")}</dt><dd><time dateTime={result.book.fetched_at}>{new Intl.DateTimeFormat(locale, {dateStyle: "medium", timeZone: "UTC"}).format(new Date(result.book.fetched_at))}</time></dd>
        </dl>
        <p className="mt-3 text-xs text-zinc-600">{t("snapshotNote")}</p>
        <ShareBook key={`${locale}:${isbn13}`} isbn13={result.book.isbn13} />
      </> : <section className="rounded-lg border border-zinc-200 p-6">
        <h1 className="text-2xl font-semibold">{t("errorTitle")}</h1>
        <p role="alert" className="mt-3 text-zinc-600">{t(result.status)}</p>
        {result.status === "unavailable" ? <a href={bookPath(locale as Language, isbn13)} className="mt-4 inline-flex min-h-11 items-center rounded border border-zinc-300 px-4 py-2 text-sm hover:bg-zinc-100">{t("retry")}</a> : null}
      </section>}
    </main>
  );
}

export default function BookDetailsPage(props: Props) {
  return <Suspense fallback={<Loading />}><Details {...props} /></Suspense>;
}
