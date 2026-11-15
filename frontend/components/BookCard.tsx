import { useTranslations } from "next-intl";

import BookDisplay from "@/components/BookDisplay";
import { ArrowIcon } from "@/components/Icons";
import { Link } from "@/i18n/navigation";
import type { Book } from "@/lib/types";

export default function BookCard({book, detailsAvailable = false}: {book: Book; detailsAvailable?: boolean}) {
  const t = useTranslations("BookCard");
  const action = detailsAvailable ? <Link href={`/books/${book.isbn13}`} prefetch={false} className="details-link">{t("viewDetails")}<ArrowIcon /></Link> : null;
  return <BookDisplay book={book} rank={book.rank} action={action}>
    <div className="recommendation">
      <p className="reason-label">{t("whyFits")}</p>
      <p className="reason-text">{book.reason}</p>
      <p className="reason-note">{t("aiReason")}</p>
    </div>
  </BookDisplay>;
}
