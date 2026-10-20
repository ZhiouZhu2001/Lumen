import { notFound } from "next/navigation";
import * as rootParams from "next/root-params";
import { hasLocale } from "next-intl";
import { getRequestConfig } from "next-intl/server";

import { routing } from "./routing";

// Runs on the server for each request: picks the language and its messages.
export default getRequestConfig(async () => {
  // Read the [locale] segment of the URL (Next.js 16.3+)
  const requested = await rootParams.locale();
  if (!hasLocale(routing.locales, requested)) {
    notFound(); // e.g. /fr → 404
  }
  const locale = requested;

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});