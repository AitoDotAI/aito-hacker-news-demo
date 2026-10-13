"""Simulate Hacker News front-page traffic against a deployment of the demo.

Each virtual visitor does what an HN reader does: loads the page, reads
for a while, tries one to four titles with pauses in between, and leaves.
Titles are drawn from a mix, because the mix decides the cache hit rate:

  - the example titles on the page             (everyone clicks these)
  - a small shared pool                        (titles from the HN thread)
  - fresh unique titles                        (people typing their own)

Arrivals ramp up to `--users` concurrent visitors and hold there, which
is how a front-page hour looks: a step up, then a plateau.

Usage:
    # 5-minute smoke at 20 visitors against a local backend
    uv run python -m scripts.loadtest --base http://localhost:8401 \\
        --users 20 --minutes 5

    # the launch rehearsal: 300 concurrent visitors for an hour, against
    # the TEST slot (never production; never during the day, shared.aito.ai
    # serves customers)
    uv run python -m scripts.loadtest --base https://<test-host>/hacker-news \\
        --users 300 --minutes 60 --json data/loadtest.json

Read-only against Aito (the demo only issues queries), but it is real
load on the Aito instance behind the target. Coordinate before running
it at scale.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

EXAMPLES = [
    "Show HN: A minimal Postgres client written in Rust",
    "OpenAI announces new model with breakthrough reasoning",
    "I built a todo app over the weekend",
]
SHARED = [
    "Show HN: Predict how your HN title will do, with honest error bars",
    "Ask HN: What are you working on?",
    "Why SQLite is fast",
    "Show HN: I made a terminal-based spreadsheet",
    "The unreasonable effectiveness of boring technology",
    "Launch HN: We're building a database that predicts",
]
WORDS = (
    "rust postgres sqlite llm agent compiler kernel browser linux gpu startup "
    "database wasm typescript python zig emacs vim open source privacy search "
    "inference cache queue protocol network crypto robotics climate battery"
).split()
DOMAINS = [None, None, "github.com", "nytimes.com", "arstechnica.com",
           "substack.com", "medium.com", "youtube.com"]

# Fraction of submitted titles drawn from each pool.
MIX = {"example": 0.35, "shared": 0.25, "unique": 0.40}


@dataclass
class Stats:
    lat: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    status: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    cache: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    per_min: dict[int, list[float]] = field(default_factory=lambda: defaultdict(list))
    errors_per_min: dict[int, int] = field(default_factory=lambda: defaultdict(int))


def pick_title(rng: random.Random) -> str:
    r = rng.random()
    if r < MIX["example"]:
        return rng.choice(EXAMPLES)
    if r < MIX["example"] + MIX["shared"]:
        return rng.choice(SHARED)
    words = rng.sample(WORDS, rng.randint(3, 6))
    prefix = rng.choice(["", "", "Show HN: ", "Ask HN: "])
    return prefix + " ".join(words).capitalize()


def predict_body(rng: random.Random, title: str) -> dict:
    # Same shape the page sends: current hour/day, explicit title_length.
    now = datetime.now(timezone.utc)
    return {
        "title": title,
        "domain": rng.choice(DOMAINS),
        "hour_utc": now.hour,
        "day_of_week": now.weekday(),
        "title_length": len(title),
        "similar_limit": 8,
    }


async def timed(client: httpx.AsyncClient, kind: str, stats: Stats, t0: float,
                method: str, url: str, **kw) -> httpx.Response | None:
    start = time.perf_counter()
    minute = int((time.time() - t0) // 60)
    try:
        r = await client.request(method, url, **kw)
        ms = (time.perf_counter() - start) * 1000
        stats.lat[kind].append(ms)
        stats.status[f"{kind}:{r.status_code}"] += 1
        if kind == "predict":
            stats.per_min[minute].append(ms)
            stats.cache[r.headers.get("x-cache", "none")] += 1
        if r.status_code >= 400:
            stats.errors_per_min[minute] += 1
        return r
    except httpx.HTTPError as e:
        stats.status[f"{kind}:{type(e).__name__}"] += 1
        stats.errors_per_min[minute] += 1
        return None


async def visitor(base: str, client: httpx.AsyncClient, stats: Stats,
                  rng: random.Random, t0: float, assets: list[str]) -> None:
    await timed(client, "page", stats, t0, "GET", f"{base}/")
    for a in assets:
        await timed(client, "asset", stats, t0, "GET", a)
    await asyncio.sleep(rng.uniform(5, 20))           # reading the page
    for _ in range(rng.choice([1, 1, 2, 2, 3, 4])):
        title = pick_title(rng)
        await timed(client, "predict", stats, t0, "POST", f"{base}/api/predict-hn",
                    json=predict_body(rng, title))
        await asyncio.sleep(rng.uniform(10, 40))      # reading the result


async def discover_assets(client: httpx.AsyncClient, base: str) -> list[str]:
    """The page's own JS/CSS, so the static tier carries its real share."""
    try:
        html = (await client.get(f"{base}/")).text
    except httpx.HTTPError:
        return []
    origin = re.match(r"https?://[^/]+", base).group(0)
    paths = re.findall(r'(?:src|href)="(/[^"]+\.(?:js|css))"', html)
    return [origin + p for p in dict.fromkeys(paths)][:12]


async def run(base: str, users: int, minutes: float, ramp_s: float, seed: int) -> Stats:
    stats = Stats()
    rng = random.Random(seed)
    limits = httpx.Limits(max_connections=users * 2, max_keepalive_connections=users)
    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        assets = await discover_assets(client, base)
        print(f"target {base}; {len(assets)} static assets per page view")
        t0 = time.time()
        deadline = t0 + minutes * 60
        active: set[asyncio.Task] = set()
        last_report = t0

        while time.time() < deadline:
            elapsed = time.time() - t0
            target = users if elapsed >= ramp_s else max(1, int(users * elapsed / ramp_s))
            while len(active) < target:
                vrng = random.Random(rng.random())
                t = asyncio.create_task(visitor(base, client, stats, vrng, t0, assets))
                active.add(t)
                t.add_done_callback(active.discard)
            if time.time() - last_report >= 60:
                last_report = time.time()
                m = int((last_report - t0) // 60) - 1
                lat = stats.per_min.get(m, [])
                if lat:
                    print(f"  min {m:>3}: {len(active):>4} visitors  {len(lat):>5} predicts  "
                          f"p50 {pct(lat, 50):>6.0f}ms  p95 {pct(lat, 95):>6.0f}ms  "
                          f"errors {stats.errors_per_min.get(m, 0)}", flush=True)
            await asyncio.sleep(0.5)

        for t in list(active):
            t.cancel()
        await asyncio.gather(*active, return_exceptions=True)
    return stats


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p / 100))]


def summary(stats: Stats, minutes: float) -> dict:
    out: dict = {"by_kind": {}, "status": dict(stats.status), "cache": dict(stats.cache)}
    for kind, xs in stats.lat.items():
        out["by_kind"][kind] = {
            "n": len(xs),
            "per_s": len(xs) / (minutes * 60),
            "p50_ms": pct(xs, 50), "p95_ms": pct(xs, 95), "p99_ms": pct(xs, 99),
            "max_ms": max(xs), "mean_ms": statistics.fmean(xs),
        }
    out["per_minute"] = [
        {"minute": m, "n": len(v), "p50_ms": pct(v, 50), "p95_ms": pct(v, 95),
         "errors": stats.errors_per_min.get(m, 0)}
        for m, v in sorted(stats.per_min.items())
    ]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True, help="demo root URL, e.g. https://host/hacker-news")
    ap.add_argument("--users", type=int, default=20, help="concurrent visitors at plateau")
    ap.add_argument("--minutes", type=float, default=5)
    ap.add_argument("--ramp", type=float, default=120, help="seconds to reach --users")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", metavar="PATH")
    args = ap.parse_args(argv)

    stats = asyncio.run(run(args.base.rstrip("/"), args.users, args.minutes,
                            args.ramp, args.seed))
    s = summary(stats, args.minutes)
    print()
    for kind, k in s["by_kind"].items():
        print(f"{kind:<8} n={k['n']:>6}  {k['per_s']:>6.2f}/s  p50 {k['p50_ms']:>6.0f}ms  "
              f"p95 {k['p95_ms']:>6.0f}ms  p99 {k['p99_ms']:>6.0f}ms  max {k['max_ms']:>6.0f}ms")
    print(f"cache    {s['cache']}")
    bad = {k: v for k, v in s["status"].items() if not k.endswith((":200", ":304"))}
    print(f"non-200  {bad or 'none'}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"args": vars(args), **s}, f, indent=2)
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
