"""Fetch a corpus of Hacker News stories from the public Algolia HN API
into a newline-delimited JSON file shaped for upload to Aito's
`hn_submissions` table.

Algolia's HN endpoint paginates and applies a hard 1000-hit ceiling per
numeric-filter window. So we walk a date range in fixed-size windows and
fetch each window's pages; if a window is "full" the window is too wide
and we recurse into halves until everything fits or we give up at the
minimum window size.

Usage:
    uv run python -m scripts.fetch_corpus \\
        --output data/submissions.ndjson \\
        --start 2023-01-01 --end 2026-05-01

    # quick seed for prototyping
    uv run python -m scripts.fetch_corpus \\
        --output data/seed.ndjson --start 2026-01-01 --end 2026-05-01

Algolia HN: https://hn.algolia.com/api  — no auth, public, polite usage expected.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
HITS_PER_PAGE = 1000
MAX_PAGES = 1  # Algolia HN: page*hitsPerPage must stay <= 1000 → 1 page max at 1000/page


def score_bucket(score: int) -> str:
    if score < 10:
        return "flop"
    if score < 50:
        return "low"
    if score < 150:
        return "mid"
    if score < 500:
        return "hit"
    return "viral"


def derive_domain(url: str | None, title: str) -> str:
    """Domain from URL, or "self" for Ask HN / Show HN with no URL."""
    if not url:
        return "self"
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return "unknown"
    if not host:
        return "unknown"
    return host[4:] if host.startswith("www.") else host


def normalize(hit: dict) -> dict | None:
    """Map Algolia hit → row matching the Aito schema. Drop unusable rows."""
    title = hit.get("title")
    if not title:
        return None
    points = hit.get("points")
    if points is None:
        return None
    created_at_i = hit.get("created_at_i")
    if created_at_i is None:
        return None

    score = int(points)
    comments = int(hit.get("num_comments") or 0)
    url = hit.get("url") or ""
    dt = datetime.fromtimestamp(int(created_at_i), tz=timezone.utc)
    return {
        "id": str(hit.get("objectID")),
        "title": title,
        "url": url,
        "domain": derive_domain(url or None, title),
        "score": score,
        "comments": comments,
        "hour_utc": dt.hour,
        "day_of_week": dt.weekday(),  # 0 = Monday
        "is_show_hn": title.startswith("Show HN:"),
        "is_ask_hn": title.startswith("Ask HN:"),
        "title_length": len(title),
        "success_bucket": score_bucket(score),
        "front_page": score >= 50,
        "created_at": dt.isoformat(),
    }


@dataclass
class WindowResult:
    hits: list[dict]
    total: int  # Algolia's reported nbHits (may exceed returned hits if >1000)


def fetch_window(client: httpx.Client, start_ts: int, end_ts: int, page: int = 0) -> WindowResult:
    params = {
        "tags": "story",
        "numericFilters": f"created_at_i>={start_ts},created_at_i<{end_ts}",
        "hitsPerPage": HITS_PER_PAGE,
        "page": page,
    }
    for attempt in range(4):
        try:
            r = client.get(ALGOLIA_URL, params=params, timeout=30.0)
            if r.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            return WindowResult(hits=data.get("hits", []), total=int(data.get("nbHits", 0)))
        except httpx.HTTPError as e:
            if attempt == 3:
                raise
            time.sleep(1.0 * (attempt + 1))
            print(f"    retry after error: {e}", file=sys.stderr)
    raise RuntimeError("unreachable")


def walk(
    client: httpx.Client,
    start: datetime,
    end: datetime,
    out_file,
    seen_ids: set[str],
    counters: dict,
    limit: int | None,
    min_window_seconds: int = 3600,
) -> bool:
    """Fetch all stories in [start, end). If the window holds >1000 hits,
    recurse into halves so we stay under Algolia's 1000-hit ceiling.

    Returns False if limit hit (caller should stop), True otherwise.
    """
    start_ts = int(start.timestamp())
    end_ts = int(end.timestamp())

    res = fetch_window(client, start_ts, end_ts, page=0)

    span_seconds = end_ts - start_ts
    if res.total > HITS_PER_PAGE and span_seconds > min_window_seconds:
        mid = start + (end - start) / 2
        if not walk(client, start, mid, out_file, seen_ids, counters, limit, min_window_seconds):
            return False
        return walk(client, mid, end, out_file, seen_ids, counters, limit, min_window_seconds)

    if res.total > HITS_PER_PAGE:
        # Couldn't split further; we'll lose the tail. Note it and continue.
        counters["truncated_windows"] += 1
        print(
            f"  ! window {start.isoformat()}..{end.isoformat()} has {res.total} hits, "
            f"only the first {HITS_PER_PAGE} are reachable",
            file=sys.stderr,
        )

    for hit in res.hits:
        oid = str(hit.get("objectID"))
        if oid in seen_ids:
            continue
        seen_ids.add(oid)
        row = normalize(hit)
        if row is None:
            continue
        out_file.write(json.dumps(row, ensure_ascii=False) + "\n")
        counters["written"] += 1
        if limit is not None and counters["written"] >= limit:
            return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output", required=True, help="path to NDJSON output file")
    ap.add_argument("--start", default="2023-01-01", help="UTC date YYYY-MM-DD (inclusive)")
    ap.add_argument("--end", default="2026-05-01", help="UTC date YYYY-MM-DD (exclusive)")
    ap.add_argument(
        "--window-days",
        type=int,
        default=1,
        help="initial window size in days (subdivides on overflow). Default 1.",
    )
    ap.add_argument("--limit", type=int, default=None, help="cap total rows written")
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="seconds to sleep between window fetches (be polite)",
    )
    args = ap.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(args.end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if start >= end:
        ap.error("--start must be before --end")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    counters = {"written": 0, "truncated_windows": 0}

    print(f"Fetching HN stories {args.start} → {args.end} ({args.window_days}d windows)")
    t0 = time.time()

    with httpx.Client() as client, out_path.open("w", encoding="utf-8") as out:
        cur = start
        while cur < end:
            nxt = min(cur + timedelta(days=args.window_days), end)
            keep_going = walk(client, cur, nxt, out, seen_ids, counters, args.limit)
            elapsed = time.time() - t0
            rate = counters["written"] / max(elapsed, 0.001)
            print(
                f"  {cur.date()} → {nxt.date()}: total written={counters['written']:>7} "
                f"({rate:.0f}/s, elapsed={elapsed:.0f}s)",
                flush=True,
            )
            if not keep_going:
                print(f"  reached --limit={args.limit}, stopping")
                break
            cur = nxt
            time.sleep(args.sleep)

    elapsed = time.time() - t0
    print(
        f"\nDone. Wrote {counters['written']} rows to {out_path} in {elapsed:.0f}s. "
        f"Truncated windows: {counters['truncated_windows']}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
