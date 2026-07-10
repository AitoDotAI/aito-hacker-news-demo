"""Search the title × posting-time space to find the best slot for a
launch post about "Predictive Application" (Aito).

Two-stage search to keep the Aito-call count manageable:

1. Score a list of candidate titles at a single sane posting time
   (Tue 14:00 UTC — the canonical HN window). Rank by front-page %.
2. Take the top-K titles and sweep day × hour to find the best slot
   per title. Report the global maximum + a stability hint (how much
   the prediction actually moves with time, given our 9.5k-row corpus).

Usage:
    uv run python -m scripts.find_best_post

Output is plain text; pipe to `tee` if you want to keep it.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Iterable

from src.aito_client import AitoClient
from src.config import load_config
from src.predict_service import PredictRequest, predict_hn

# Variants for "Predictive Application" / Aito launch.
TITLES: list[str] = [
    "Show HN: Predictive Application",
    "Show HN: Introducing Predictive Application",
    "Show HN: Aito – an inference database for structured prediction",
    "Show HN: Predict any column of your data with one HTTP call",
    "Show HN: a database that predicts answers instead of returning rows",
    "Show HN: We replaced our ML pipeline with a predictive database",
    "Introducing Predictive Application",
    "Predictive Application: structured prediction as a database primitive",
    "The predictive database we wish existed",
    "Why we built a predictive database instead of training a model",
    "Aito: predict any field in milliseconds, no model training",
    "Show HN: Aito – calibrated probabilities from a single SQL-like query",
]

# Default posting slot for the title bake-off.
DEFAULT_DAY = 1   # Tuesday (0=Mon..6=Sun)
DEFAULT_HOUR = 14  # 14:00 UTC

# Stage-2 sweep ranges. Restrict to active hours so we don't churn
# through dead-of-night slots that nobody posts in anyway.
SWEEP_DAYS = list(range(0, 7))             # Mon..Sun
SWEEP_HOURS = list(range(6, 23))           # 06:00 .. 22:00 UTC
TOP_K_FOR_SWEEP = 3                        # how many titles get the full time sweep

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class Score:
    title: str
    day: int
    hour: int
    front_page_pct: float
    modal_bucket: str
    expected_score: float
    expected_comments: float


def score_one(c: AitoClient, title: str, day: int, hour: int) -> Score:
    req = PredictRequest(title=title, day_of_week=day, hour_utc=hour)
    r = predict_hn(c, req)
    return Score(
        title=title,
        day=day,
        hour=hour,
        front_page_pct=r.headline["front_page_pct"],
        modal_bucket=r.estimated_score.most_likely_bucket,
        expected_score=r.estimated_score.expected,
        expected_comments=r.estimated_comments,
    )


def stage1_bake_off(c: AitoClient) -> list[Score]:
    print(f"\n[1/2] Bake-off at default slot: {DAY_NAMES[DEFAULT_DAY]} {DEFAULT_HOUR:02d}:00 UTC")
    print(f"      Scoring {len(TITLES)} title candidates...\n")
    scores = [score_one(c, t, DEFAULT_DAY, DEFAULT_HOUR) for t in TITLES]
    scores.sort(key=lambda s: -s.front_page_pct)

    print(f"  {'front-page %':>14}  {'modal':>6}  {'exp pts':>8}  {'exp cmts':>8}  title")
    print(f"  {'-' * 14}  {'-' * 6}  {'-' * 8}  {'-' * 8}  -----")
    for s in scores:
        print(
            f"  {s.front_page_pct:>13.1f}%  {s.modal_bucket:>6}  "
            f"{s.expected_score:>8.1f}  {s.expected_comments:>8.1f}  {s.title}"
        )
    return scores


def stage2_time_sweep(c: AitoClient, top_titles: Iterable[str]) -> list[Score]:
    print(
        f"\n[2/2] Time sweep for top {TOP_K_FOR_SWEEP} titles "
        f"({len(SWEEP_DAYS)} days × {len(SWEEP_HOURS)} hours = "
        f"{len(SWEEP_DAYS) * len(SWEEP_HOURS)} slots each).\n"
    )

    everything: list[Score] = []
    for title in top_titles:
        title_scores: list[Score] = []
        for day in SWEEP_DAYS:
            for hour in SWEEP_HOURS:
                title_scores.append(score_one(c, title, day, hour))
        everything.extend(title_scores)

        # Per-title best/worst + spread
        best = max(title_scores, key=lambda s: s.front_page_pct)
        worst = min(title_scores, key=lambda s: s.front_page_pct)
        spread = best.front_page_pct - worst.front_page_pct

        print(f"  >> {title}")
        print(
            f"     best:  {best.front_page_pct:5.1f}%  ({DAY_NAMES[best.day]} {best.hour:02d}:00 UTC)"
        )
        print(
            f"     worst: {worst.front_page_pct:5.1f}%  ({DAY_NAMES[worst.day]} {worst.hour:02d}:00 UTC)"
        )
        print(f"     spread across time slots: {spread:.1f} pp")
        print()

    return everything


def summary(everything: list[Score]) -> None:
    print("\n──────── final recommendation ────────")
    top = sorted(everything, key=lambda s: -s.front_page_pct)[:5]
    print(f"\n  Top 5 title × time combinations by predicted front-page %:")
    print(f"  {'front-page %':>14}  {'when':<22}  {'modal':>6}  title")
    for s in top:
        when = f"{DAY_NAMES[s.day]} {s.hour:02d}:00 UTC"
        print(
            f"  {s.front_page_pct:>13.1f}%  {when:<22}  {s.modal_bucket:>6}  {s.title}"
        )
    best = top[0]
    print()
    print(f"  Winner: {best.title!r}")
    print(f"  Posted: {DAY_NAMES[best.day]} {best.hour:02d}:00 UTC")
    print(f"  Predicted front-page chance: {best.front_page_pct:.1f}%")
    print(f"  Expected upvotes: {best.expected_score:.0f}  (modal: {best.modal_bucket})")
    print(f"  Expected comments: {best.expected_comments:.0f}")


def main() -> int:
    c = AitoClient(load_config())
    stage1 = stage1_bake_off(c)
    top_titles = [s.title for s in stage1[:TOP_K_FOR_SWEEP]]
    everything = stage2_time_sweep(c, top_titles)
    # Include stage1 results too so single-slot scores are comparable.
    everything.extend(stage1)
    summary(everything)
    return 0


if __name__ == "__main__":
    sys.exit(main())
