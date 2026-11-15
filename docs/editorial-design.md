# Editorial interface design

## Approved direction and implementation boundary

On 2026-11-15 the user approved the literary-journal/old-bookshop direction and
then explicitly requested implementation. The three reviewed concepts cover
desktop search/results, mobile search/results, and saved-book details/sharing.
The implementation baseline is `80e5765`; this is round 29 on
`codex/update-29-editorial-redesign`.

## Visual inventory

The accepted desktop reference is 1448x1086; the mobile art-direction reference
is 1024x1536. References remain outside the repository under the user's local
`lumen-vintage-concept-v1` visualization directory. They are design references,
not runtime screenshots or catalog assets.

| Element | Design rule |
| --- | --- |
| Background | Warm ivory `#F5F1E8`, with a quiet paper character; never white or tinted by an image overlay. |
| Ink and action | Ink `#26372F`, forest action `#29483C`, ivory button text. |
| Accent and rules | Restrained terracotta `#A3543A`; warm separators `#CFC6B8`. |
| Typography | Literary serif headings/wordmark/actions, readable sans-serif text and inputs. Locally hosted Libre Baskerville normal/italic and Source Sans 3; retain their third-party font licenses. |
| Geometry | Open editorial rows and fine rules; small control radii, generous whitespace, no nested card grid or floating panels. |
| Header | Lumen wordmark and dot, two locale controls with an underlined active state. |
| Hero | Two-line literary heading, two supporting lines and one engraved-book illustration. Hide the illustration on narrow screens. |
| Search | Visible query label, query input and primary action, then the three existing optional filters. Wrap controls under enlarged text. |
| Results | Real ordered recommendations with rank, catalog cover, title, author, metadata, reason, description disclosure, store links and detail/share action. |
| Details | Back navigation, same-ISBN locale links, large real catalog cover and title, metadata/source/date strip, separate public sharing action. |
| Icons | Consistent thin SVG arrows, copy and disclosure chevrons; decorative icons hidden from assistive technology. |
| Interaction | Native labels/disclosures, 44px minimum controls, visible focus, retained search cancellation/error recovery and copy fallback. Reduced-motion support. |

The matching engraved books asset has transparent edges and no text; it has no
color overlay. The wordmark and all UI copy remain real text. Book covers always
come from catalog data, never the illustrative book jackets in the concepts.

## Copy and component ownership

The Spanish hero uses “Tu próxima” / “buena historia.”, “Cuéntanos qué te apetece
leer.” and “Encuentra libros reales, en inglés y español.” The primary action is
“Encontrar libros”; results use “Entre estas páginas”. English receives the same
hierarchy and meaning. The page title semantics may change from the wordmark to
the hero; this adds no visible eyebrow, badge or filler copy.

Shared chrome owns the wordmark/footer; shared icons own arrow/copy/chevrons;
`BookDisplay` owns real bibliography, covers, rating, disclosure and channels;
`BookCard` adds rank, the real streamed reason and gated details action;
`ShareBook` retains its existing public-link state machine. Search/session,
metadata lookup/cache and locale-routing logic retain their existing owners.

## Necessary production differences

The concepts show selected sample books and illustrative covers/reasons. The
application must render actual returned data and cannot promise a particular
title, rating, cover, count or stock. Dynamic text can increase row height.
Existing AI-reason attribution, source-labelled ratings, filter constraints,
channel caveats and saved-snapshot warnings remain visible even where the
concept omits them. These are correctness/privacy requirements, not new product
features. The mobile reference is an illustration of direction; actual layout
must reflow at 320px, at enlarged text and with long catalog content.

No accounts, favorites, personalization, new catalog/model source, pricing,
availability claim, search graph change, paid service or public deployment is
part of this design. The current daily allowance and durable ledger remain.

## Font sources

Font files are vendored from the official Google Fonts repository directories
[Libre Baskerville](https://github.com/google/fonts/tree/main/ofl/librebaskerville)
and [Source Sans 3](https://github.com/google/fonts/tree/main/ofl/sourcesans3).
Their OFL files are retained beside the fonts; these notices concern third-party
font software and do not assign project authorship. Browser visits and builds
use the vendored files through `next/font/local`.
