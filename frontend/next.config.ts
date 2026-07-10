import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
  // Static export in production — FastAPI's StaticFiles(html=True) mount in
  // src/app.py serves the built files from frontend/out, and /api/* routes
  // are handled by FastAPI from the same port. One process, one port.
  // Dev still runs `next dev` + uvicorn separately, so dev keeps the
  // rewrite below.
  ...(isDev ? {} : { output: "export" }),

  trailingSlash: true,
  // Match what StaticFiles(html=True) resolves (`/foo/` → `foo/index.html`).
  // Skip the auto-redirect so dev `/api/*` requests pass through whichever
  // form the client sent.
  skipTrailingSlashRedirect: true,

  // Dev only: proxy /api/* to the FastAPI backend on its dev port.
  // In production FastAPI serves /api/* from the same origin as the static
  // export, so the rewrite isn't needed.
  ...(isDev
    ? {
        async rewrites() {
          return [
            {
              source: "/api/:path*",
              destination: `http://localhost:${process.env.BACKEND_PORT || "8401"}/api/:path*`,
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
