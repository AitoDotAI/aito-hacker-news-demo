"""Measure how well the demo actually predicts Hacker News outcomes.

The demo makes a falsifiable claim — "this title has an N% chance of
reaching the front page" — so it should be held to a falsifiable test.
This script runs that test and prints the numbers, including the
unflattering ones.

Method
------
The Aito table is a fixed corpus with a known date range. We hold out
submissions created *after* the corpus cutoff, so nothing we score has
ever been seen by the index. For each held-out submission we ask the
demo's own `predict_hn` path for p(front_page) and compare against
what actually happened (front_page := score >= 50, matching
`scripts/fetch_corpus.py`).

Reported
--------
  AUC            Rank-discrimination. 0.5 = coin flip, 1.0 = perfect.
                 The headline number: can it tell hits from flops at all?
  Decile lift    Front-page rate among the top-decile predictions vs. the
                 base rate. The "is this useful in practice" number.
  Calibration    Predicted probability vs. observed frequency, bucketed.
                 A 40% prediction should hit 40% of the time.
  Ablation       The same AUC computed from single fields, to show which
                 input actually carries the signal.

Usage
-----
    uv run python -m scripts.evaluate                  # 700 held-out posts
    uv run python -m scripts.evaluate --n 300          # faster
    uv run python -m scripts.evaluate --no-ablation
    uv run python -m scripts.evaluate --json out.json

Requires AITO_API_URL + AITO_API_KEY (same as the app). Read-only —
this script never writes to the Aito instance.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

import httpx

from src.aito_client import AitoClient, AitoError
from src.config import load_config
from src.predict_service import TABLE, PredictRequest, predict_hn

ALGOLIA = "https://hn.algolia.com/api/v1/search_by_date"

# front_page := score >= 50 — must match scripts/fetch_corpus.py, or we'd
# be scoring against a different label than the one the corpus was built on.
FRONT_PAGE_THRESHOLD = 50

# Holdout is drawn from a window starting this many days after the corpus
# cutoff, so nothing scored can have leaked into the index. The gap also
# skips the period right after the cutoff where a partial-day fetch might
# have caught some rows.
HOLDOUT_GAP_DAYS = 7
# ...and ending this many days before now, so scores have settled. HN
# submissions keep accruing points for roughly 48h; a week is ample.
SETTLE_DAYS = 14

DEFAULT_N = 700
CONCURRENCY = 8
SEED = 42


# ── Corpus introspection ─────────────────────────────────────────────

def corpus_bounds(aito: AitoClient) -> tuple[datetime, datetime, int]:
    """(oldest, newest, row_count) of the live Aito table.

    We ask the index rather than reading data/submissions.ndjson because
    the local file and the deployed table can drift, and the thing we're
    evaluating is the deployed table.
    """
    def edge(direction: str) -> datetime:
        r = aito.search(
            table=TABLE, where={}, limit=1,
            order_by={f"${direction}": "created_at"},
        )
        hits = r.get("hits") or []
        if not hits:
            raise SystemExit(f"{TABLE} is empty — nothing to evaluate against.")
        return _parse_ts(hits[0]["created_at"])

    total = aito.search(table=TABLE, where={}, limit=0).get("total", 0)
    return edge("asc"), edge("desc"), int(total)


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ── Holdout sampling ─────────────────────────────────────────────────

@dataclass
class Post:
    title: str
    domain: str | None
    score: int
    hour_utc: int
    day_of_week: int
    created_at: str

    @property
    def front_page(self) -> bool:
        return self.score >= FRONT_PAGE_THRESHOLD


# The holdout window can span years. Algolia's search_by_date returns hits
# newest-first, so naively paging one query would sample only the last few
# days of the window — and HN's composition drifts (AI titles in 2026 look
# nothing like 2024). Instead we cut the window into slices and sample each,
# so the holdout is spread across the whole period.
HOLDOUT_SLICES = 12


def fetch_holdout(start: datetime, end: datetime, want: int) -> list[Post]:
    """Pull stories created in [start, end) straight from HN's own API.

    Stratified by time: the window is cut into `HOLDOUT_SLICES` equal
    slices and we draw an equal share from each, so the sample reflects
    the whole holdout period rather than just its most recent days.
    Within a slice, hits come back newest-first; that ordering is
    unrelated to score, which is the only thing we measure.
    """
    span = (end - start) / HOLDOUT_SLICES
    per_slice = max(1, -(-want // HOLDOUT_SLICES))  # ceil
    out: list[Post] = []
    seen: set[str] = set()

    with httpx.Client(timeout=30.0) as client:
        for i in range(HOLDOUT_SLICES):
            s_start = start + span * i
            s_end = start + span * (i + 1)
            got = 0
            for page in range(4):
                if got >= per_slice:
                    break
                try:
                    r = client.get(ALGOLIA, params={
                        "tags": "story",
                        "numericFilters": (
                            f"created_at_i>={int(s_start.timestamp())},"
                            f"created_at_i<{int(s_end.timestamp())}"
                        ),
                        "hitsPerPage": 200,
                        "page": page,
                    })
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    print(f"  warn: slice {i} page {page} failed ({e}); skipping")
                    break
                hits = r.json().get("hits") or []
                if not hits:
                    break
                for h in hits:
                    post = _normalize(h)
                    if post and post.title not in seen:
                        seen.add(post.title)
                        out.append(post)
                        got += 1

    random.Random(SEED).shuffle(out)
    return out[:want]


def _normalize(hit: dict) -> Post | None:
    title = (hit.get("title") or "").strip()
    points = hit.get("points")
    ts = hit.get("created_at_i")
    if not title or points is None or not ts:
        return None
    url = hit.get("url") or ""
    domain = None
    if url:
        parts = url.split("/")
        if len(parts) > 2 and parts[2]:
            domain = parts[2].lower().removeprefix("www.")
    when = datetime.fromtimestamp(ts, tz=timezone.utc)
    return Post(
        title=title,
        domain=domain,
        score=int(points),
        hour_utc=when.hour,
        day_of_week=when.weekday(),  # 0=Mon..6=Sun, matches the schema
        created_at=when.isoformat(),
    )


# ── Metrics ──────────────────────────────────────────────────────────

def auc(scored: list[tuple[float, bool]]) -> float:
    """Probability that a random positive outranks a random negative.

    Computed by rank-sum (Mann-Whitney U) so it's O(n log n) and handles
    ties as half-credit.
    """
    pos = sum(1 for _, y in scored if y)
    neg = len(scored) - pos
    if not pos or not neg:
        return float("nan")
    ranked = sorted(scored, key=lambda t: t[0])
    ranks: dict[int, float] = {}
    i = 0
    while i < len(ranked):
        j = i
        while j + 1 < len(ranked) and ranked[j + 1][0] == ranked[i][0]:
            j += 1
        avg = (i + j) / 2 + 1  # 1-based, averaged across the tie group
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    rank_sum = sum(ranks[k] for k, (_, y) in enumerate(ranked) if y)
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def decile_lift(scored: list[tuple[float, bool]]) -> dict[str, float]:
    ranked = sorted(scored, key=lambda t: -t[0])
    k = max(1, len(ranked) // 10)
    base = sum(1 for _, y in scored if y) / len(scored)
    top = sum(1 for _, y in ranked[:k] if y) / k
    bottom = sum(1 for _, y in ranked[-k:] if y) / k
    return {
        "n_per_decile": k,
        "base_rate": base,
        "top_decile_rate": top,
        "bottom_decile_rate": bottom,
        "lift": (top / base) if base else float("nan"),
    }


CALIBRATION_EDGES = [0.0, 0.05, 0.10, 0.20, 0.35, 0.60, 1.01]


def calibration(scored: list[tuple[float, bool]]) -> list[dict[str, Any]]:
    rows = []
    for lo, hi in zip(CALIBRATION_EDGES, CALIBRATION_EDGES[1:]):
        sel = [(p, y) for p, y in scored if lo <= p < hi]
        if not sel:
            continue
        rows.append({
            "range": f"{lo:.2f}–{hi:.2f}",
            "n": len(sel),
            "mean_predicted": sum(p for p, _ in sel) / len(sel),
            "observed": sum(1 for _, y in sel if y) / len(sel),
        })
    return rows


# ── Scoring runs ─────────────────────────────────────────────────────

def _p_front_page(resp: dict) -> float:
    for hit in resp.get("hits") or []:
        if hit.get("feature") is True:
            return float(hit.get("$p") or 0.0)
    return 0.0


def score_full_model(aito: AitoClient, posts: list[Post]) -> list[tuple[float, bool]]:
    """Score via the demo's real code path, so we measure what ships."""
    def one(post: Post) -> tuple[float, bool] | None:
        try:
            r = predict_hn(aito, PredictRequest(
                title=post.title, domain=post.domain,
                hour_utc=post.hour_utc, day_of_week=post.day_of_week,
                similar_limit=3,
            ))
            return r.headline["front_page_pct"] / 100.0, post.front_page
        except (AitoError, ValueError):
            return None

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        return [r for r in ex.map(one, posts) if r is not None]


def score_ablation(
    aito: AitoClient, posts: list[Post], build_where: Callable[[Post], dict | None],
) -> list[tuple[float, bool]]:
    """Score using a single hand-built `where`, to isolate one field."""
    def one(post: Post) -> tuple[float, bool] | None:
        where = build_where(post)
        if where is None:
            return None
        try:
            r = aito.predict(table=TABLE, where=where,
                             predict_field="front_page", limit=2)
            return _p_front_page(r), post.front_page
        except (AitoError, ValueError):
            return None

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        return [r for r in ex.map(one, posts) if r is not None]


ABLATIONS: dict[str, Callable[[Post], dict | None]] = {
    "title only":     lambda p: {"title": p.title},
    "domain only":    lambda p: {"domain": p.domain} if p.domain else None,
    "length only":    lambda p: {"title_length": {"$numeric": len(p.title)}},
    "hour only":      lambda p: {"hour_utc": {"$numeric": p.hour_utc}},
    "title + domain": lambda p: ({"title": p.title, "domain": p.domain}
                                 if p.domain else None),
}


# ── Reporting ────────────────────────────────────────────────────────

def report(result: dict[str, Any]) -> None:
    w = sys.stdout.write
    c = result["corpus"]
    h = result["holdout"]

    w("\n" + "=" * 66 + "\n")
    w("  Does this demo actually predict Hacker News?\n")
    w("=" * 66 + "\n\n")

    w(f"corpus    {c['rows']:,} rows, {c['oldest'][:10]} → {c['newest'][:10]}\n")
    w(f"holdout   {h['n']:,} submissions, {h['start'][:10]} → {h['end'][:10]} "
      f"(after the corpus ends — never indexed)\n")
    w(f"label     front_page := score >= {FRONT_PAGE_THRESHOLD}; "
      f"{h['base_rate']:.1%} of the holdout qualifies\n\n")

    m = result["full_model"]
    w(f"AUC (as shipped)           {m['auc']:.3f}")
    w("   ← 0.50 is a coin flip\n")
    d = m["decile"]
    w(f"top-decile front-page rate {d['top_decile_rate']:.1%}  "
      f"(vs {d['base_rate']:.1%} base = {d['lift']:.2f}x lift)\n")
    w(f"bottom-decile              {d['bottom_decile_rate']:.1%}\n\n")

    w("calibration — a 40% prediction should happen 40% of the time:\n")
    w(f"  {'predicted':>12}  {'observed':>9}  {'n':>5}\n")
    for row in m["calibration"]:
        flag = ""
        if row["n"] >= 10:
            ratio = row["observed"] / row["mean_predicted"] if row["mean_predicted"] else 0
            if ratio < 0.6:
                flag = "  ← overconfident"
            elif ratio > 1.7:
                flag = "  ← underconfident"
        w(f"  {row['mean_predicted']:>11.1%}  {row['observed']:>8.1%}  "
          f"{row['n']:>5}{flag}\n")

    if result.get("ablation"):
        w("\nwhere the signal comes from (AUC from a single field):\n")
        for name, a in result["ablation"].items():
            w(f"  {name:<16} {a['auc']:.3f}   n={a['n']:>4}   "
              f"top-decile lift {a['decile']['lift']:.2f}x\n")

    w("\n")


# ── Main ─────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=DEFAULT_N,
                    help=f"holdout size (default {DEFAULT_N})")
    ap.add_argument("--no-ablation", action="store_true",
                    help="skip the per-field ablation (faster)")
    ap.add_argument("--json", metavar="PATH",
                    help="also write the full report as JSON")
    ap.add_argument(
        "--holdout-start", metavar="YYYY-MM-DD",
        help=(
            "pin the holdout window start instead of deriving it from the "
            "corpus cutoff. Use this to score the same submissions against "
            "two different corpora — otherwise each run picks its own window "
            "and the comparison is confounded."
        ),
    )
    ap.add_argument("--holdout-end", metavar="YYYY-MM-DD",
                    help="pin the holdout window end (see --holdout-start)")
    args = ap.parse_args(argv)

    def _pin(s: str) -> datetime:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    cfg = load_config()
    aito = AitoClient(cfg)
    # Print what we actually queried, env included — a report that claims
    # to measure production while pointing at a branch is worse than none.
    print(f"Aito: {cfg.api_base}  (env: {cfg.aito_env or 'master'})")

    oldest, newest, rows = corpus_bounds(aito)
    start = (_pin(args.holdout_start) if args.holdout_start
             else newest + timedelta(days=HOLDOUT_GAP_DAYS))
    end = (_pin(args.holdout_end) if args.holdout_end
           else datetime.now(timezone.utc) - timedelta(days=SETTLE_DAYS))
    if start >= end:
        raise SystemExit(
            f"Corpus ends {newest:%Y-%m-%d}, which leaves no settled holdout "
            f"window. Nothing to evaluate against."
        )
    # A pinned window is only a valid holdout if the corpus genuinely ends
    # before it — otherwise we would be scoring rows the index has seen.
    if start < newest + timedelta(days=HOLDOUT_GAP_DAYS):
        raise SystemExit(
            f"Holdout starts {start:%Y-%m-%d} but the corpus runs to "
            f"{newest:%Y-%m-%d}. That overlaps the index — the result would "
            f"be a memorisation score, not a prediction score."
        )

    print(f"corpus {rows:,} rows ending {newest:%Y-%m-%d}; "
          f"sampling holdout from {start:%Y-%m-%d} → {end:%Y-%m-%d}")
    posts = fetch_holdout(start, end, args.n)
    if len(posts) < 50:
        raise SystemExit(f"Only {len(posts)} holdout posts — too few to score.")

    base_rate = sum(1 for p in posts if p.front_page) / len(posts)
    print(f"scoring {len(posts)} held-out submissions "
          f"({base_rate:.1%} reached the front page)…")

    t0 = time.time()
    full = score_full_model(aito, posts)
    print(f"  full model: {len(full)} scored in {time.time() - t0:.0f}s")

    result: dict[str, Any] = {
        "corpus": {
            "rows": rows,
            "oldest": oldest.isoformat(),
            "newest": newest.isoformat(),
            "url": cfg.api_base,
            "env": cfg.aito_env or "master",
        },
        "holdout": {
            "n": len(posts),
            "start": start.isoformat(),
            "end": end.isoformat(),
            "base_rate": base_rate,
        },
        "full_model": {
            "auc": auc(full),
            "decile": decile_lift(full),
            "calibration": calibration(full),
            "n_scored": len(full),
        },
    }

    if not args.no_ablation:
        result["ablation"] = {}
        for name, build in ABLATIONS.items():
            t0 = time.time()
            scored = score_ablation(aito, posts, build)
            if not scored:
                continue
            result["ablation"][name] = {
                "auc": auc(scored),
                "decile": decile_lift(scored),
                "n": len(scored),
            }
            print(f"  ablation {name}: {len(scored)} scored "
                  f"in {time.time() - t0:.0f}s")

    report(result)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"wrote {args.json}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
