# Book-link previews

Saved-book pages emit localized page titles, descriptions, Open Graph fields and
Twitter card fields. The book title remains the original bibliographic title;
the surrounding English/Spanish description identifies its catalog authors and
ISBN. Missing authors are omitted instead of invented. Previews use the public
stored-book response, not a reader's search, recommendation reason, source
description or request query parameters.

## Request and rendering behavior

The existing validated detail loader still checks the requested ISBN, rejects
wrong-identity/malformed replies, uses `cache: no-store` and bounds its request
at five seconds. A request-local React cache shares its result between metadata
generation and the visible detail page. This matters because the loader's abort
signal opts out of the framework's automatic fetch memoization. No persistent
cross-request book cache is added; a later request can receive updated data.

Next.js keeps its existing streaming behavior. Regular clients can receive
metadata later in the HTML stream; recognized HTML-limited bots receive it in
the initial head. The implementation does not override the framework's bot list,
Cache Components setting, page skeleton, share button or API proxy.

## Covers and error states

Only absolute HTTPS cover URLs on `books.google.com` or
`covers.openlibrary.org` are used in previews. URLs with credentials, nonstandard
ports, fragments or recognized key/token/search/reason parameters are omitted.
An absent or unusable cover produces a text summary card. Preview text is
normalized and bounded without splitting Unicode code points. Original catalog
records and visible book details are not mutated.

Invalid ISBNs, missing saved books and unavailable/malformed responses produce
distinct localized descriptions, generic unavailable titles, no book image and
`noindex, nofollow`. This is metadata behavior: existing streamed detail-error
responses can still be HTTP 200. Unsupported locale paths retain the middleware's
relative 307 default-locale redirect followed by a 404, with no book lookup.
HTTP-status-aware detail-error responses remain separate work.

No canonical public URL, Open Graph origin or author-profile URL is invented.
An approved public origin can be configured in a later deployment round. The
existing copy-link control continues to use the current origin and public
locale/ISBN path while dropping search parameters and fragments.

## Verification and limits

Native tests cover the two translations, bibliography, absent authors/covers,
noindex states, metadata privacy, Unicode bounds and cover URL rules. Production
Next.js HTTP checks use a controlled loopback backend to verify actual metadata,
HTML-limited bot head delivery, one upstream lookup, cross-request cover updates,
invalid-ISBN rejection, malformed/wrong-identity replies and the existing timeout.

`backend/evals/results/book-share-20261114-round27.json` retains the initial
28-case probe with one incorrect direct-404 expectation. The separate
`book-share-20261114-round27-verified.json` passes all 28 checks after following
the existing relative locale redirect to its final 404; implementation and
thresholds were unchanged. These captures are explicitly fixture-backed and are
not the 20-case recommendation gate.

This verification makes no model, real catalog or database calls and does not
confirm live image availability, actual social-platform caching, clipboard
permissions, visual browser layout, public ingress or production deployment.
Share providers may cache previews independently; a later local snapshot update
does not guarantee immediate changes on a third-party platform.
