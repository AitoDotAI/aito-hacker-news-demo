# CLAUDE.md — agent instructions for this demo

This file is read by Claude Code (and similar agents) when working in this repo. Keep it tight; put narrative in `docs/` if it grows.

## What this is

An Aito demo bootstrapped from `aito-demo-server/template/`. Production shape:

- **Python 3.12 + FastAPI + uvicorn** backend (`src/app.py`)
- **Next.js 16 static export** frontend (`frontend/` → `frontend/out/`)
- **One uvicorn process** serves both `/api/*` and `/` (via FastAPI's `StaticFiles(html=True)` mount at the bottom of `app.py`)
- **Aito as data backend** — no other DB

This demo runs in `aito-demos-unified` (one container, all demos), behind nginx routing by `Host` header, at `<demo-name>.aito.ai`.

## Conventions enforced by the platform — DO NOT drift

The aito-demo-server platform (`/home/arau/episto/src/aito-demo-server/`) generates the Dockerfile, nginx config, and supervisord config from `demos.config.yaml`. It assumes this demo:

| Convention | Lives at | Don't change without coordinating the platform |
|---|---|---|
| Backend entry | `src/app.py` defines `app: FastAPI` | The platform runs `uvicorn src.app:app --host 0.0.0.0 --port ${PORT}` |
| Frontend output | `frontend/out/` after `npx next build` | The platform's `build.frontend_build` runs `cd frontend && npm ci && npx next build` |
| Static mount | `app.mount("/", StaticFiles(...))` at the END of `src/app.py` | Must be last so it doesn't shadow `/api/*` |
| `/health` | Returns 200 cheaply, no Aito call | Platform's nginx routes `<demo>.aito.ai/health` here |
| `/api/health` | Returns 200 + `aito_connected: bool` + `aito_url` | Used for readiness; OK if it touches Aito |
| Lockfiles | `uv.lock` + `frontend/package-lock.json` committed | Build uses `uv sync --frozen` + `npm ci` |
| Env contract | `AITO_API_URL` + `AITO_API_KEY` | Platform remaps from `AITO_<NAME>_*` via demos.config.yaml's `env:` block |

If you genuinely need to break one of these, update both this demo AND the platform's expectations in the same PR.

## Local dev

```bash
./do install    # uv sync + npm install (one-time)
./do dev        # uvicorn on :8401 + next dev on :3000, hot-reload both
./do build      # produces frontend/out/ (only needed for prod-shape smoke test)
./do backend    # production-shape: uvicorn only, serves static if frontend/out/ exists
./do test-book  # run booktest suite (snapshot tests, see CHEATSHEET.md)
./do screenshot-teaser  # render assets/teaser.html → assets/teaser.png (1200×630)
./do screenshot-pages   # full-page screenshots of key paths (regression)
./do inspect-mobile     # iPhone-sized screenshots for layout review
```

## Where to start when building this demo

1. **Replace `src/app.py`'s `/api/example`** — that's the placeholder. Add your routes. Each one delegates to Aito via the shared `AitoClient` (`src/aito_client.py`). Keep handlers thin; factor logic to `src/<thing>_service.py` as needed.
2. **Replace `frontend/app/page.tsx`** — the placeholder fetches `/api/example` and renders the result via the shell (`TopBar` + `AitoPanel`). Replace with your real UI. Build your own `AitoPanelConfig` for each page.
3. **The shell components in `frontend/components/shell/`** (`TopBar`, `Nav`, `AitoPanel`, `ErrorState`, `Analytics`, `LatencyBadge`) come from accounting's reference impl. Generalize / extend as needed; don't remove the AitoPanel — it's the visual identity of "Aito demo".
4. **The prediction primitives in `frontend/components/prediction/`** (`PredictionBadge`, `ConfidenceBar`, `WhyTooltip`, `PredictedField`, `WhyCards`, `LiftHint`) — drop into your UI wherever you display an Aito prediction. They render the calibrated-confidence + $why-explanation pattern uniformly across demos.
5. **`frontend/lib/aito.ts`** is for browser-side Aito calls (rare); the default pattern is browser → FastAPI (`/api/*`) → Aito via `AitoClient`. `frontend/lib/api.ts`'s `apiFetch` is the standard wrapper (handles error envelope + emits latency events for LatencyBadge).
6. **Replace `assets/teaser.html` + `assets/teaser.png`** — the landing page (aito.ai) thumbnails come from here.
7. **Update `README.md`** to describe what this demo actually is.
8. **Walk `CHECKLIST.md`** before declaring done.

## When you write new code

- **Aito queries** — see `CHEATSHEET.md` for the standard predict / match / search patterns. Don't reinvent wheels.
- **Test snapshots** — non-deterministic Aito outputs (probabilities, similarities) are easier to assert against with `booktest` than `pytest assert ==`. See `tests/test_aito_book.py`.
- **Caching** — if you call Aito on every request, the demo feels slow. Cache cheap derivatives in-memory (`functools.lru_cache` for pure-input cases) or use a small disk cache for warmup. Check what `aito-accounting-demo/src/cache.py` does for the established pattern.
- **Logging** — `print()` works; supervisord forwards stdout/stderr to Azure Log Analytics. Structured logging optional; if used, tag with `demo: <name>` for the unified-container log split.

## Common pitfalls

- **`uv sync --frozen` fails** → `uv.lock` is out of date; run `uv lock` and re-commit.
- **Static export errors** → check `frontend/next.config.ts` still has `output: "export"` in production; Next.js features like Image Optimization, ISR, or server components don't work with static export.
- **`/api/*` 404 in production but works in dev** → likely added a route AFTER the `app.mount` line; the mount shadows it. Move the route above the mount.
- **`/api/*` works in production but 404 in dev** → the dev rewrite in `next.config.ts` proxies to `BACKEND_PORT` (default 8401); make sure your backend is on the matching port.
- **CORS errors** → for direct-from-browser Aito calls, set CORS on the Aito instance (not in FastAPI). For same-origin calls (recommended), no CORS needed.

## Releasing a change

The aito-demo-server platform tracks each demo's `main` branch by default. So:

1. PR your change in this repo
2. Merge to `main`
3. In aito-azure: `./do deploy-demos` — rebuilds the unified image (your latest `main` is pulled at build time via `git ls-remote`) and updates the Web App

If you want to deploy a feature branch for testing without merging, in aito-demo-server change this demo's `ref:` in `demos.config.yaml` from `main` to your branch name temporarily, then revert + rebuild after merge.

## Files you can ignore as an agent

- `frontend/.next/`, `frontend/out/`, `frontend/node_modules/`, `.venv/` — build artifacts / installed deps
- `books/` — booktest output, regenerated by tests
- `*.lock` files — managed by `uv` and `npm`, don't hand-edit

## Latency badge — how it works

`apiFetch` (frontend/lib/api.ts) reads the `X-Aito-Ms` / `X-Aito-Calls` / `X-Aito-Ops` response headers from every `/api/*` response. `LatencyBadge` subscribes to those events and shows the last Aito round-trip in the topbar.

`src/app.py`'s middleware sets those headers based on `aito.last_call` (the AitoClient records the most recent call's op + ms). If you bypass `AitoClient` (e.g., call Aito directly with raw httpx in a route), set the headers yourself in the response so the badge keeps working.

## Pointers

- [CHEATSHEET.md](./CHEATSHEET.md) — Aito query cookbook
- [CHECKLIST.md](./CHECKLIST.md) — pre-launch checklist (analytics, product sheet, teaser, etc.)
- `/home/arau/episto/src/aito-demo-server/README.md` — the platform that hosts this demo
- `/home/arau/episto/src/aito-demo-server/aito-demo-framework.md` — the shared design system (850 lines, covers shell, prediction, design tokens, analytics, testing). Read this when you need to extend the patterns.
- `/home/arau/episto/src/aito-azure/do` — deploy mechanics (don't run from here; this demo is one of N)
- The reference impl for everything in here: `/home/arau/episto/src/aito-accounting-demo/`
