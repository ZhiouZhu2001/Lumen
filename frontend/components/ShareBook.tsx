"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { bookPath } from "@/lib/book-details";
import type { Language } from "@/lib/types";

export default function ShareBook({isbn13}: {isbn13: string}) {
  const t = useTranslations("BookDetails");
  const locale = useLocale() as Language;
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<"copied" | "copyManually" | null>(null);
  const [copying, setCopying] = useState(false);

  async function copyLink() {
    // Build from the origin and public identity only; discard queries and fragments.
    const link = new URL(bookPath(locale, isbn13), window.location.origin).href;
    setUrl(link);
    setCopying(true);
    setStatus(null);
    try {
      await navigator.clipboard.writeText(link);
      setStatus("copied");
    } catch {
      setStatus("copyManually");
    } finally {
      setCopying(false);
    }
  }

  return (
    <section className="mt-6 rounded-lg border border-zinc-200 p-4" aria-label={t("share")}>
      <button type="button" onClick={copyLink} disabled={copying} className="min-h-11 rounded bg-black px-4 py-2 text-sm text-white hover:bg-zinc-800 focus-visible:outline-2 focus-visible:outline-offset-4 disabled:opacity-50">
        {t("share")}
      </button>
      <p className="mt-2 text-xs text-zinc-600">{t("shareNote")}</p>
      {url ? <label className="mt-3 block text-sm">{t("linkLabel")}
        <input readOnly value={url} onFocus={event => event.currentTarget.select()} className="mt-1 min-h-11 w-full rounded border border-zinc-300 px-3 py-2 text-sm" />
      </label> : null}
      <p role="status" aria-live="polite" className="mt-2 text-sm text-zinc-600">{status ? t(status) : ""}</p>
    </section>
  );
}
