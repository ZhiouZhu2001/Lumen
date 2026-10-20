// JSON shape returned by POST /api/search (see backend app/sources/schemas.py).

export type Rating = {
    value: string; // Pydantic sends Decimal as a string, e.g. "4.3"
    count: number;
    source: string;
};

export type Book = {
    isbn13: string;
    title: string;
    authors: string[];
    published_year: number | null;
    cover_url: string | null;
    rating: Rating | null;
};

// The two book languages Lumen supports (must match the backend's Language).
export type Language = "en" | "es";
