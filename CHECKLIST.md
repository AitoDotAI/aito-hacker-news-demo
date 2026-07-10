# Demo readiness checklist

Walk this before declaring a demo "done". Items grouped by concern; order within a group doesn't matter much.

## 1. Code

- [ ] `src/app.py`'s `/api/example` replaced with the demo's actual routes
- [ ] `/health` still returns 200 cheaply (no Aito call) — don't accidentally turn it into a readiness probe
- [ ] `/api/health` returns `aito_connected: true` against the production Aito DB
- [ ] `frontend/app/page.tsx` replaced with the real UI (placeholder hello card removed)
- [ ] `src/config.py` extended for any extra env vars the demo needs (fail-loud on missing)
- [ ] `frontend/lib/aito.ts` used for direct-from-browser Aito calls; not duplicated inline
- [ ] No `extra_processes` needed in `demos.config.yaml` (i.e., single uvicorn process serves both `/api/*` and `/`)
- [ ] `uv.lock` and `frontend/package-lock.json` committed and current

## 2. Aito data

- [ ] DB created on `shared.aito.ai` (production) and a `dev` branch for local hacking
- [ ] Schema loaded; `_predict` returns sensible probabilities on 20 hand-picked test inputs (sanity check)
- [ ] Read-only API key issued (verify it can't write or admin)
- [ ] CORS configured on the Aito DB — restrict to `<demo>.aito.ai` only, not `*`
- [ ] Row count in the right ballpark for predict accuracy (typically 50k+ for categorical predict on text)
- [ ] `scripts/load-data.py` (or equivalent) committed so the corpus can be reproduced

## 3. Branding & teaser

- [ ] `assets/teaser.html` exists — designed at 1200×630, dark navy bg (`#0c0f41`), purple accent (`#7C5CFC`), white sans-serif
- [ ] `assets/teaser.png` generated from teaser.html via `./do screenshot-teaser`
- [ ] Teaser tells the demo's value prop in one glance (title + 1 metric / illustration) — not a generic screenshot
- [ ] Mobile layout verified — `./do inspect-mobile` shows no horizontal scroll, no overlapping text, touch targets ≥44px
- [ ] Page title + meta description set in `frontend/app/layout.tsx`
- [ ] Favicon set (`frontend/app/icon.png` or via metadata)
- [ ] OG image set (often the same as teaser.png; configured in layout.tsx metadata)

## 4. Analytics & funnel

- [ ] Amplitude wired up — `NEXT_PUBLIC_AMPLITUDE_KEY` env var read in frontend, init in `app/layout.tsx`
- [ ] GA4 wired up — `NEXT_PUBLIC_GA4_MEASUREMENT_ID` env var read, gtag init in `app/layout.tsx`
- [ ] Both keys added to `aito-demo-server/.env.local` AND to Azure App Settings (via aito-azure)
- [ ] Page-view event tagged with `surface: '<demo>'` (so dashboards can split traffic by demo)
- [ ] Key interaction tracked (e.g., `predict_clicked`, `result_viewed`)
- [ ] CTA to `aito.ai/trial` has UTM: `?utm_source=<demo>&utm_medium=demo&utm_campaign=launch_<week>`

## 5. Marketing surface

- [ ] **Product sheet** drafted — 1-page PDF or markdown with: what it does, who it's for, screenshot/teaser, "how to try" CTA. Lives in `docs/product-sheet.md` (or PDF in `assets/`).
- [ ] Launch one-liner agreed (what you'd write in a tweet, LinkedIn post, HN title)
- [ ] First-comment ammo written and pinned in a notes file (the meta-loop comment for HN, the "what this proves" for LinkedIn)
- [ ] Soft-launch list: 2-3 trusted people to share with before public

## 6. Tests

- [ ] `tests/test_health_book.py` passes — basic API smoke
- [ ] `tests/test_aito_book.py` passes — Aito-connected smoke (snapshot of schema or a known-stable predict)
- [ ] Mobile screenshot from `./do inspect-mobile` reviewed and committed (`docs/screenshots/mobile-home.png`)
- [ ] Full-page screenshot from `./do screenshot-pages` reviewed (regression baseline)

## 7. Platform integration

- [ ] Demo entry added to `aito-demo-server/demos.config.yaml` (`./do add-demo <name>`)
- [ ] `env:` block in the yaml entry remaps `AITO_<NAME>_API_URL/KEY` → `AITO_API_URL/KEY`
- [ ] `env:` block also remaps analytics: `AMPLITUDE_BROWSER_KEY` → `NEXT_PUBLIC_AMPLITUDE_KEY`, same for GA4
- [ ] `teaser:` block has title, tagline, one_liner, vertical, order, thumbnail path
- [ ] `assets/teaser.png` copied to `aito-demo-server/landing/thumbnails/<name>.png`
- [ ] `aito-demo-server/.env.local` has the per-demo secrets (AITO_<NAME>_*)
- [ ] `./do check` in aito-demo-server passes (no validation errors)
- [ ] `./do build && ./do up` in aito-demo-server boots the demo locally; `curl -H 'Host: <name>.aito.ai' http://localhost:8080/` returns 200

## 8. Deploy

- [ ] Code merged to `main` (assuming demos.config.yaml tracks `main`; otherwise SHA bumped)
- [ ] Secrets in Azure: `aito-azure` operator adds `AITO_<NAME>_API_URL` + `AITO_<NAME>_API_KEY` to the unified Web App's App Settings
- [ ] `aito-azure/do deploy-demos` run — image rebuilt + Web App updated
- [ ] DNS: `<name>.aito.ai` CNAME points to the unified Web App's defaultHostName; `asuid.<name>.aito.ai` TXT record set
- [ ] Custom domain bound + managed cert issued on the Web App (`aito-azure/scripts/deployment/bind-custom-domain.sh`)
- [ ] `https://<name>.aito.ai/` returns 200 from a fresh browser (cold cache, no auth, no VPN)
- [ ] `https://<name>.aito.ai/health` returns 200
- [ ] Mobile + desktop both smoke-checked at the real URL

## 9. Post-launch

- [ ] Analytics dashboard set up — pageviews, key event, trial-CTA conversion (Amplitude or GA, your call)
- [ ] Mission Control bookmark — for watching Aito query volume + latency on the new instance
- [ ] First-week metric target written down (e.g., "5k queries logged, 10 trial signups attributed")
- [ ] Calendar entry for 30-day review — pull the numbers, decide if it gets a follow-up post / amplification / sunset
- [ ] Failure mode plan: who pages if `<name>.aito.ai` goes down? (today: no one — it's `/health` 200 manual)

---

## What "done" means

A demo is done when:
1. A fresh browser session can complete the full intended UX without errors
2. The teaser is shareable as-is on HN/LinkedIn/Reddit
3. Trial-CTA conversion is being tracked end-to-end
4. The product sheet exists so sales can attach it to a follow-up email
5. `./do check` is green in aito-demo-server and the demo is live at `https://<name>.aito.ai`

Anything below items 1-5 = unfinished. Anything beyond = polish (always optional; ship first).
