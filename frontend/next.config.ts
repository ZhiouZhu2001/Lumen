import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin();

// Where the FastAPI backend runs.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  // Container builds trace a minimal server; native builds keep their workflow.
  output: process.env.NEXT_OUTPUT_STANDALONE === "1" ? "standalone" : undefined,
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Allow the backend's 60-second search deadline and terminal SSE frames.
    proxyTimeout: 70_000,
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Send every /api/... request from the browser on to the backend.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
  // Book covers come from these two sites; next/image only loads allowed hosts.
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "books.google.com" },
      { protocol: "https", hostname: "covers.openlibrary.org" },
    ],
  },
};

export default withNextIntl(nextConfig);
