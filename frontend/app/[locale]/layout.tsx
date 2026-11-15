import type { Metadata } from "next";
import localFont from "next/font/local";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";

import { routing } from "@/i18n/routing";
import PreferencesProvider from "@/components/PreferencesProvider";

import "../globals.css";

const reader = localFont({
  src: "../fonts/reader-regular.woff2",
  variable: "--font-reader",
  display: "swap",
});

const literary = localFont({
  src: [
    {path: "../fonts/literary-regular.woff2", weight: "400 700", style: "normal"},
    {path: "../fonts/literary-italic.woff2", weight: "400 700", style: "italic"},
  ],
  variable: "--font-literary",
  display: "swap",
  adjustFontFallback: "Times New Roman",
});

export const metadata: Metadata = {
  title: "Lumen",
  description: "AI book recommendations with real books",
};

// Build both language versions ahead of time: /es and /en.
export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
}: LayoutProps<"/[locale]">) {
  // Comes from i18n/request.ts, which also rejects unknown languages (404)
  const locale = await getLocale();
  const t = await getTranslations("Site");

  return (
    <html
      lang={locale}
      className={`${reader.variable} ${literary.variable} h-full antialiased`}
    >
      <body>
        <a href="#main-content" className="skip-link">{t("skip")}</a>
        <NextIntlClientProvider>
          <PreferencesProvider language={locale}>{children}</PreferencesProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
