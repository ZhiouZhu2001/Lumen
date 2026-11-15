import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Link } from "@/i18n/navigation";

export function Masthead({children}: {children: ReactNode}) {
  return <header className="masthead">
    <Link href="/" className="wordmark" aria-label="Lumen">Lumen<span aria-hidden="true">.</span></Link>
    {children}
  </header>;
}

export function SiteFooter() {
  const t = useTranslations("Site");
  return <footer className="site-footer">{t("footer")}</footer>;
}
