import type { NextConfig } from "next";

// Where the FastAPI backend runs.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
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
    return [{ source: "/api/:path", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
