"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { CopyIcon } from "@/components/Icons";
import { bookPath } from "@/lib/book-details";
import type { Language } from "@/lib/types";

export default function ShareBook({isbn13}: {isbn13: string}) {
  const t = useTranslations("BookDetails");
  const locale = useLocale() as Language;
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<"copied" | "copyManually" | null>(null);
  const [copying, setCopying] = useState(false);
  const linkField = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (status === "copyManually") linkField.current?.focus();
  }, [status, url]);

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
      // The effect handles first mount; this also supports immediate retries.
      linkField.current?.focus();
    } finally {
      setCopying(false);
    }
  }

  return (
    <section className="share-book" aria-label={t("share")}>
      <div><h2>{t("shareTitle")}</h2><p>{t("shareNote")}</p></div>
      <button type="button" onClick={copyLink} disabled={copying} className="primary-button"><CopyIcon />{t("share")}</button>
      {url ? <label className="share-field">{t("linkLabel")}
        <input ref={linkField} readOnly value={url} onFocus={event => event.currentTarget.select()} className="field" />
      </label> : null}
      <p role="status" aria-live="polite" className="share-feedback">{status ? t(status) : ""}</p>
    </section>
  );
}
