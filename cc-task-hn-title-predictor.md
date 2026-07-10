# HN Title Predictor — Demo Brief

## What this is

A single-page web app that predicts Hacker News performance for a given submission title (and optional metadata: domain, hour, day-of-week). Pure browser-side calls to a public Aito instance. No backend.

Dual purpose:
1. **Marketing artifact** — designed to be posted on HN, Reddit, LinkedIn. Self-referential hook ("predict your own HN submission, including this one").
2. **Data collection** — every query hitting Aito is logged. You learn what titles people test, what they think works, and what actually does.

Fits the Packaged IP / vertical demo pattern. Companion to `accounting.aito.ai`, `erp.aito.ai`, `ecommerce.aito.ai`. URL: `hn.aito.ai`.

## Why this works as a HN launch vehicle

- **Meta-loop:** post it to HN, the title of the submission is itself a test case. First comment shows the predicted score for the submission's own title.
- **Universally relatable to the HN crowd:** every reader has wondered why their submission flopped.
- **Quiet-win-friendly:** even if upvotes are low, exposure + indexability is the goal. People bookmark prediction tools.
- **No funnel friction:** no signup, no email gate. Tool first, "this runs on Aito" second, free trial CTA third.

## Architecture

```
Browser (static HTML/JS)
   │
   └──> Aito instance at hn-predictor.aito.app
         ├── Table: hn_submissions (corpus)
         └── Read-only API key embedded in client
```

Single HTML file. No build step required, but Vite/esbuild fine if it helps. Tailwind via CDN. Vanilla JS or tiny Preact — no React tree-shake overhead needed.

Brand: dark navy `#121830` / `#0c0f41` bg, white sans-serif, purple accent `#7C5CFC`. Match other Aito demos.

## Data corpus

**Source:** HN BigQuery public dataset (`bigquery-public-data.hacker_news.full`) OR Algolia HN API for incremental fetch.

**Filter:**
- `type = 'story'`
- `dead IS NULL AND deleted IS NULL`
- `score IS NOT NULL`
- Date range: last 3 years (recent enough to reflect current taste, large enough sample)
- Exclude `ask` / `poll` types — focus on link + Show HN submissions

**Target size:** 200k–500k rows. Aito handles this comfortably; trial row limits don't apply to this instance (production trial).

**Schema (Aito table `hn_submissions`):**

| Field | Type | Notes |
|---|---|---|
| `title` | Text | analyzer: english |
| `domain` | String | extracted from URL, e.g. `github.com`, `nytimes.com`, `self` for Ask/Show HN |
| `hour_utc` | Int | 0–23 |
| `day_of_week` | Int | 0–6, 0 = Monday |
| `is_show_hn` | Boolean | title starts with "Show HN:" |
| `is_ask_hn` | Boolean | title starts with "Ask HN:" |
| `title_length` | Int | character count, bucketed in UI |
| `success_bucket` | String | derived target: `flop` (<10), `low` (10–49), `mid` (50–149), `hit` (150–499), `viral` (500+) |
| `front_page` | Boolean | score >= 50 — simpler binary target for some queries |
| `score` | Int | raw, for reference only — don't predict directly, predict buckets |
| `comments` | Int | optional secondary target |

**Why buckets not raw score:** raw score is log-distributed and noisy. Buckets give cleaner predict-probability results in the UI ("78% chance this hits front page"). This is the standard Aito pattern — predict categorical, not regression.

**Loading:**
```bash
# Pseudo-code, adjust to current aito-cli
aito create-table hn_submissions ./schema.json
aito upload-batch hn_submissions ./submissions.ndjson --batch-size 10000
```

## Predict queries

Two queries the UI fires in parallel on submit:

**1. Bucket probability** — main result:
```json
POST /api/v1/_predict
{
  "from": "hn_submissions",
  "where": {
    "title": "<user input>",
    "domain": "<user input or null>",
    "hour_utc": <user input>,
    "day_of_week": <user input>,
    "is_show_hn": <derived from title prefix>
  },
  "predict": "success_bucket",
  "limit": 5
}
```

Returns probabilities for each bucket. Display as horizontal stacked bar (flop → viral, color-graded).

**2. Front-page binary** — headline number:
```json
POST /api/v1/_predict
{
  "from": "hn_submissions",
  "where": { /* same as above */ },
  "predict": "front_page",
  "limit": 2
}
```

Returns `{true: 0.34, false: 0.66}`. UI shows "34% chance of front page" as the big number.

**3. Optional — similar submissions** (`_match` or `_search`):
```json
POST /api/v1/_search
{
  "from": "hn_submissions",
  "where": { "title": "<user input>" },
  "orderBy": "$similarity",
  "limit": 5
}
```

Show "Similar past submissions: [title] — 234 points, [title] — 4 points." This is the "aha" — same words, wildly different outcomes. Educates about the noise inherent in HN.

## UI flow

**Screen 1 — Input (single screen, no scroll on desktop):**
- Big title input (textarea, autofocus)
- Optional row: domain, hour (defaults to "now"), day (defaults to "today")
- "Predict" button (purple, prominent)
- Below: "First time? Try one of these:" → 3 example titles (one flop, one mid, one viral), click to populate

**Screen 2 — Result (same page, slides in below input):**
- Big headline number: **"34% chance of front page"**
- Stacked probability bar: flop / low / mid / hit / viral with %s
- "Similar past submissions" list — 3 to 5 with score, clickable to HN
- Small text: "Predicted in 47ms by Aito, an inference database"
- Tiny CTA: "Want predictions on your own data? aito.ai/trial"

**Self-referential first-comment ammo:** when *you* post this to HN, your first comment is "I ran the title of this very submission through it: predicted 23% front page chance. Let's see." Then update with the actual result later. That's the loop that gets resubmissions when people re-share.

## Logging & data harvest

Aito logs every query server-side (already does — check `mission control` instance dashboard). For this demo specifically:

- Add a lightweight client-side beacon: on every predict, send `{title, domain, hour, day, predicted_bucket, predicted_pct}` to a logging endpoint. Could be:
  - Mission Control event ingestion if available
  - Or pipe to Amplitude (already in your stack)
  - Or a single Aito table `predictor_queries` that you write to (yes, write from browser is fine for a public demo; rate-limit by IP)

Weekly batch: pull `predictor_queries`, segment by query patterns. **Outputs:**
- "What people think will succeed" vs. "what actually does" — blog post material
- Title clusters (compare to your own draft titles before launching anything)
- Domain frequency — who else's stuff are people testing?

## Tracking on the marketing side

- UTM on the trial CTA: `?utm_source=hn-predictor&utm_medium=demo&utm_campaign=show_hn_w21`
- GA on the page itself
- Amplitude event: `predict_clicked`, `example_clicked`, `cta_clicked`

## Launch sequence

**Pre-launch checklist:**
- [ ] Corpus loaded, predictions sanity-checked (run 20 known titles, eyeball results)
- [ ] CORS enabled on Aito instance for `hn.aito.ai` only — not `*` (rate-limit protection)
- [ ] Read-only API key — verify it can't write or admin
- [ ] Mobile layout works (50% of HN traffic is mobile)
- [ ] OG image: dark navy bg, "Will your HN post hit front page?" + Aito logo
- [ ] First-comment draft written and pinned in a notes file

**Launch order:**
1. Quiet soft-launch — share with Emil, a few HN regulars you trust. Get a sanity read.
2. Show HN: title format = "Show HN: I built a tool that predicts HN front-page chance, using a predictive database"
   - Tuesday 09:00–10:00 EEST window
   - First comment within 60s: the meta-loop comment with the self-prediction
3. LinkedIn — personal post first, link in first comment per your rule. Company reshare after.
4. Reddit: r/dataisbeautiful (good fit — predictions are visualizable), r/programming. Wait until r/MachineLearning ban lifts ~May 26.
5. Hold one more wave for 2 weeks later: "What I learned from 10k predictions" follow-up post — uses harvested query data.

## What success looks like

- **Primary metric:** trial signups from `utm_source=hn-predictor` over 30 days. Target: 30+. Realistic floor: 10.
- **Secondary metric:** queries logged. Target: 5k+ in first week (means it spread). 50k+ = it worked.
- **Tertiary metric:** at least one inbound from a technical buyer who says "I saw your HN thing."

The previous two HN launches in funded era had zero conversions because no funnel existed. Funnel now exists. This time the artifact itself *is* the funnel entry — much lower friction than "here's our docs page."

## What this is not

- Not a serious ML benchmark. Aito will lose to a fine-tuned BERT model on this task. That's fine — the pitch is *zero ML ceremony, structured-data inference as a database primitive*, and the demo proves the speed/simplicity claim, not SOTA accuracy.
- Not an ongoing product. One-off marketing artifact. Don't sink Mission Control reliability work into it.
- Not a replacement for the ecommerce / accounting / ERP demos. Those serve ICP outreach. This serves top-of-funnel community marketing.

## Build estimate

If Claude Code does the bulk: half a day for corpus prep, half a day for UI, half a day for polish + launch prep. ~1.5 days realistic in 15hr/week budget = one week wall-clock.

Defer if conflicts with Show HN w21 main launch. This could actually *be* the Show HN w21 launch — better hook than a performance blog post, and the performance post can ride second.
