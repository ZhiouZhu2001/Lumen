import { defineRouting } from "next-intl/routing";

// The two languages Lumen speaks. Spanish first: our users live in Spain.
export const routing = defineRouting({
    locales: ["es","en"],
    defaultLocale: "es",
});