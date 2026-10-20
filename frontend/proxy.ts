import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

// Sends "/" to "/es" (or "/en", from the browser's language).
export default createMiddleware(routing);

export const config = {
    // Skip /api (forwarded to the backend), Next.js internals and files like favicon.ico
    matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
}