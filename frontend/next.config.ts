import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// Sub-path mount. Empty by default (served at the origin root — local dev and a
// standalone subdomain deploy). aito-demo-server sets NEXT_PUBLIC_BASE_PATH at
// build time (e.g. "/hacker-news") when hosting this demo under a path on
// demos.aito.ai, so every asset URL and internal link is prefixed. Must stay in
// lockstep with lib/api.ts's API_BASE / withBase().
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  // Static export in production — FastAPI's StaticFiles(html=True) mount in
  // src/app.py serves the built files from frontend/out, and /api/* routes
  // are handled by FastAPI from the same port. One process, one port.
  // Dev still runs `next dev` + uvicorn separately, so dev keeps the
  // rewrite below.
  ...(isDev ? {} : { output: "export" }),

  // basePath also drives assetPrefix so hashed /_next/* URLs resolve under the
  // mount. Only applied when set — dev and root deploys stay at "/".
  ...(basePath ? { basePath } : {}),

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
