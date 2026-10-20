import { createNavigation } from "next-intl/navigation";

import { routing } from "./routing";

// Language-aware versions of Next.js navigation helpers.
export const { Link, redirect, usePathname, useRouter, getPathname } = 
    createNavigation(routing);
    