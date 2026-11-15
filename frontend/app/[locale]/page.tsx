"use client";

import Image from "next/image";
import { useEffect, useId, useRef, type SubmitEvent } from "react";
import { useLocale, useTranslations } from "next-intl";

import BookCard from "@/components/BookCard";
import BookCardSkeleton from "@/components/BookCardSkeleton";
import { ArrowIcon, ChevronIcon } from "@/components/Icons";
import { Masthead, SiteFooter } from "@/components/SiteChrome";
import { usePreferences } from "@/components/PreferencesProvider";
import { usePathname, useRouter } from "@/i18n/navigation";
import { useBookSearch } from "@/lib/use-book-search";
import type { Language } from "@/lib/types";

const LANGUAGES: {code: Language; label: string}[] = [
  {code: "es", label: "Español"},
  {code: "en", label: "English"},
];
const FIELD = "field";

export default function Home() {
  const language = useLocale();
  const t = useTranslations("HomePage");
  const router = useRouter();
  const pathname = usePathname();
  const setLanguage = usePreferences(state => state.setLanguage);
  const search = useBookSearch(language);
  const loading = search.status === "loading";
  const formId = useId();
  const queryInput = useRef<HTMLInputElement>(null);
  const requestedLanguage = useRef(language);

  useEffect(() => {
    if (search.status === "error" || search.status === "cancelled") {
      queryInput.current?.focus();
    }
  }, [search.status]);

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
    <div className="site-shell">
      <Masthead>
        <div role="group" aria-label={t("languageLabel")} className="locale-controls">
          {LANGUAGES.map(({code, label}) => (
            <button key={code} type="button" lang={code} onClick={() => changeLanguage(code)} aria-pressed={language === code} className="locale-link">{label}</button>
          ))}
        </div>
      </Masthead>
      <main id="main-content">
        <section className="hero" aria-labelledby={`${formId}-heading`}>
          <div>
            <h1 id={`${formId}-heading`}><span>{t("heroTitle")}</span><em>{t("heroAccent")}</em></h1>
            <p className="hero-intro"><span>{t("heroIntro")}</span><span>{t("heroSupport")}</span></p>
          </div>
          <Image src="/images/books-engraving.png" alt="" width={1904} height={816} sizes="(max-width: 672px) 1px, 480px" className="hero-art" />
        </section>

      <form onSubmit={handleSubmit} className="search-form" aria-label={t("requestLabel")}>
        <label htmlFor={`${formId}-query`} className="field-label">{t("requestLabel")}</label>
        <div className="search-line">
          <input
            ref={queryInput} id={`${formId}-query`} value={search.query} onChange={event => search.setQuery(event.target.value)}
            placeholder={t("placeholder")} minLength={3} maxLength={300} required disabled={loading}
            className={FIELD}
          />
          <div className="search-buttons">
            <button type="submit" disabled={loading} className="primary-button">
              {loading ? t("searchingButton") : t("search")}<ArrowIcon />
            </button>
            {loading ? (
              <button type="button" onClick={search.cancel} className="secondary-button">
                {t("cancel")}
              </button>
            ) : null}
          </div>
        </div>
        <div className="filters">
          <div className="filter-group">
            <label htmlFor={`${formId}-genre`}>{t("genre")}</label>
            <div className="select-wrap"><select id={`${formId}-genre`} value={search.filters.genre} onChange={event => search.setFilter("genre", event.target.value)} disabled={loading} className={FIELD} aria-describedby={`${formId}-note`}>
              <option value="">{t("any")}</option>
              <option value="historical fiction">{t("historical")}</option>
              <option value="graphic novels">{t("comics")}</option>
              <option value="manga">Manga</option>
              <option value="fantasy">{t("fantasy")}</option>
              <option value="thriller">Thriller</option>
            </select><ChevronIcon /></div>
          </div>
          <div className="filter-group">
            <label htmlFor={`${formId}-era`}>{t("era")}</label>
            <div className="select-wrap"><select id={`${formId}-era`} value={search.filters.era} onChange={event => search.setFilter("era", event.target.value)} disabled={loading} className={FIELD} aria-describedby={`${formId}-note`}>
              <option value="">{t("any")}</option>
              {["2020s", "2010s", "2000s", "1990s", "1980s"].map(value => <option key={value}>{value}</option>)}
            </select><ChevronIcon /></div>
          </div>
          <div className="filter-group">
            <label htmlFor={`${formId}-length`}>{t("length")}</label>
            <div className="select-wrap"><select id={`${formId}-length`} value={search.filters.length} onChange={event => search.setFilter("length", event.target.value)} disabled={loading} className={FIELD} aria-describedby={`${formId}-note`}>
              <option value="">{t("any")}</option>
              <option value="short">{t("short")}</option>
              <option value="medium">{t("medium")}</option>
              <option value="long">{t("long")}</option>
            </select><ChevronIcon /></div>
          </div>
        </div>
        <p id={`${formId}-note`} className="filter-note">{t("filterNote")}</p>
      </form>

      <section aria-label={t("resultsLabel")} aria-busy={loading}>
        <div className="results-heading">
          {loading || search.books.length > 0 ? <h2>{t("resultsHeading")}</h2> : null}
          <div role="status" aria-live="polite" aria-atomic="true" className="search-status">
            {status}
            {loading && search.count !== null ? ` · ${t("candidates", {count: search.count})}` : ""}
          </div>
        </div>
        {search.error ? <p role="alert" className="search-error">{t(search.error)}</p> : null}
        {loading && search.books.length === 0 ? <><BookCardSkeleton /><BookCardSkeleton /></> : null}
        {search.books.map(book => (
          <BookCard key={book.isbn13} book={book} detailsAvailable={search.status === "complete"} />
        ))}
      </section>
      </main>
      <SiteFooter />
    </div>
  );
}
