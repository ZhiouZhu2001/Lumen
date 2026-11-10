"use client";

import { useId, useRef, type SubmitEvent } from "react";
import { useLocale, useTranslations } from "next-intl";

import BookCard from "@/components/BookCard";
import BookCardSkeleton from "@/components/BookCardSkeleton";
import { usePreferences } from "@/components/PreferencesProvider";
import { usePathname, useRouter } from "@/i18n/navigation";
import { useBookSearch } from "@/lib/use-book-search";
import type { Language } from "@/lib/types";

const LANGUAGES: {code: Language; label: string}[] = [
  {code: "es", label: "Español"},
  {code: "en", label: "English"},
];
const FIELD = "min-h-11 w-full min-w-0 rounded border border-zinc-300 bg-white px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-offset-2 disabled:bg-zinc-50 disabled:text-zinc-500";

export default function Home() {
  const language = useLocale();
  const t = useTranslations("HomePage");
  const router = useRouter();
  const pathname = usePathname();
  const setLanguage = usePreferences(state => state.setLanguage);
  const search = useBookSearch(language);
  const loading = search.status === "loading";
  const formId = useId();
  const requestedLanguage = useRef(language);

  function changeLanguage(next: Language) {
    if (next === language && next === requestedLanguage.current) return;
    requestedLanguage.current = next;
    search.reset();
    setLanguage(next);
    router.replace(pathname, {locale: next});
  }

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    void search.submit();
  }

  const status = loading
    ? t(search.stage === "parsing" ? "parsing" : search.stage === "ranking" ? "ranking" : "searching")
    : search.status === "complete"
      ? t(search.limited ? "limited" : "complete", {count: search.books.length})
      : search.status === "cancelled" ? t("cancelled") : "";

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-6 sm:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Lumen</h1>
          <p className="mt-2 text-zinc-600">{t("tagline")}</p>
        </div>
        <div role="group" aria-label={t("languageLabel")} className="flex w-fit shrink-0 gap-2 text-sm">
          {LANGUAGES.map(({code, label}) => (
            <button
              key={code} type="button" lang={code}
              onClick={() => changeLanguage(code)} aria-pressed={language === code}
              className={`min-h-11 rounded border px-4 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 ${language === code ? "border-black bg-black text-white" : "border-zinc-300 hover:bg-zinc-100 active:bg-zinc-200"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-4" aria-label={t("requestLabel")}>
        <label htmlFor={`${formId}-query`} className="block text-sm font-medium">{t("requestLabel")}</label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <input
            id={`${formId}-query`} value={search.query} onChange={event => search.setQuery(event.target.value)}
            placeholder={t("placeholder")} minLength={3} maxLength={300} required disabled={loading}
            className={`${FIELD} flex-1`}
          />
          <div className="flex gap-2">
            <button type="submit" disabled={loading} className="min-h-11 flex-1 rounded bg-black px-5 py-2 text-white hover:bg-zinc-800 active:bg-zinc-700 focus-visible:outline-2 focus-visible:outline-offset-2 disabled:opacity-50">
              {loading ? t("searchingButton") : t("search")}
            </button>
            {loading ? (
              <button type="button" onClick={search.cancel} className="min-h-11 rounded border border-zinc-300 px-4 py-2 hover:bg-zinc-100 active:bg-zinc-200 focus-visible:outline-2 focus-visible:outline-offset-2">
                {t("cancel")}
              </button>
            ) : null}
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="min-w-0 text-sm">
            <label htmlFor={`${formId}-genre`}>{t("genre")}</label>
            <select id={`${formId}-genre`} value={search.filters.genre} onChange={event => search.setFilter("genre", event.target.value)} disabled={loading} className={`${FIELD} mt-1`} aria-describedby={`${formId}-note`}>
              <option value="">{t("any")}</option>
              <option value="historical fiction">{t("historical")}</option>
              <option value="graphic novels">{t("comics")}</option>
              <option value="manga">Manga</option>
              <option value="fantasy">{t("fantasy")}</option>
              <option value="thriller">Thriller</option>
            </select>
          </div>
          <div className="min-w-0 text-sm">
            <label htmlFor={`${formId}-era`}>{t("era")}</label>
            <select id={`${formId}-era`} value={search.filters.era} onChange={event => search.setFilter("era", event.target.value)} disabled={loading} className={`${FIELD} mt-1`} aria-describedby={`${formId}-note`}>
              <option value="">{t("any")}</option>
              {["2020s", "2010s", "2000s", "1990s", "1980s"].map(value => <option key={value}>{value}</option>)}
            </select>
          </div>
          <div className="min-w-0 text-sm">
            <label htmlFor={`${formId}-length`}>{t("length")}</label>
            <select id={`${formId}-length`} value={search.filters.length} onChange={event => search.setFilter("length", event.target.value)} disabled={loading} className={`${FIELD} mt-1`} aria-describedby={`${formId}-note`}>
              <option value="">{t("any")}</option>
              <option value="short">{t("short")}</option>
              <option value="medium">{t("medium")}</option>
              <option value="long">{t("long")}</option>
            </select>
          </div>
        </div>
        <p id={`${formId}-note`} className="text-xs leading-relaxed text-zinc-600">{t("filterNote")}</p>
      </form>

      <div role="status" aria-live="polite" aria-atomic="true" className="mt-4 min-h-6 text-sm text-zinc-600">
        {status}
        {loading && search.count !== null ? ` · ${t("candidates", {count: search.count})}` : ""}
      </div>
      {search.error ? <p role="alert" className="mt-4 text-sm text-red-700">{t(search.error)}</p> : null}

      <section aria-label={t("resultsLabel")} aria-busy={loading} className="mt-6 space-y-4">
        {loading && search.books.length === 0 ? <><BookCardSkeleton /><BookCardSkeleton /></> : null}
        {search.books.map(book => (
          <BookCard key={book.isbn13} book={book} detailsAvailable={search.status === "complete"} />
        ))}
      </section>
    </main>
  );
}
