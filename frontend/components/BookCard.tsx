import { useTranslations } from "next-intl";

import BookDisplay from "@/components/BookDisplay";
import { Link } from "@/i18n/navigation";
import type { Book } from "@/lib/types";

export default function BookCard({ book, detailsAvailable = false }: { book: Book; detailsAvailable?: boolean }) {
  const t = useTranslations("BookCard");
  return (
    <BookDisplay book={book}>
      <p className="mt-3 text-sm">{book.reason}</p>
      <p className="mt-1 text-xs text-zinc-500">{t("aiReason")}</p>
      {detailsAvailable ? (
        <Link href={`/books/${book.isbn13}`} prefetch={false} className="mt-2 inline-flex min-h-11 items-center rounded text-sm underline underline-offset-4 hover:text-zinc-600 focus-visible:outline-2 focus-visible:outline-offset-4">
          {t("viewDetails")}
        </Link>
      ) : null}
    </BookDisplay>
  );
}
