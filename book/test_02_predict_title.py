"""Snapshot tests for /api/predict-hn around the title
"Introducing Predictive Application" and variants.

Walks the predict_hn() pipeline against the live Aito DB on first run;
booktest's @snapshot_httpx records the calls and replays them on
subsequent runs so the test stays fast and deterministic.

Update with:
    ./do test-book --update-snapshots
"""

from __future__ import annotations

import booktest as bt

from src.aito_client import AitoClient
from src.config import load_config
from src.predict_service import PredictRequest, predict_hn


def _client() -> AitoClient:
    return AitoClient(load_config())


def _print_prediction(t: bt.TestCaseRun, title: str, res) -> None:
    t.h2(title)
    t.iln(f"front page chance: {res.headline['front_page_pct']:.1f}%  ({res.headline['label']})")
    t.iln(
        f"likely upvotes:    ~{round(res.estimated_score.most_likely_midpoint)}"
        f"  (modal bucket: {res.estimated_score.most_likely_bucket})"
    )
    t.iln(f"avg w/ long tail: {res.estimated_score.expected:.1f}")
    t.iln(f"likely comments:   ~{res.estimated_comments:.0f}")
    t.iln("")
    t.iln("bucket distribution:")
    for b in res.bucket_distribution:
        bar = "#" * max(1, round(b.probability * 30))
        t.iln(f"  {b.bucket:5}  {b.probability * 100:5.1f}%  {bar}")
    t.iln("")
    t.iln("top 3 similar past submissions:")
    for p in res.similar_posts[:3]:
        t.iln(f"  {p.score:>4} pts | {p.comments:>3} comments | {p.title[:70]}")
    t.iln("")
    t.iln("per-bucket top why-factors:")
    for b in res.bucket_distribution:
        if not b.why_factors:
            continue
        chips = "  ".join(
            f"{f.value}×{(f.weight or 0):.2f}" for f in b.why_factors[:3]
        )
        t.iln(f"  {b.bucket:>6}  {chips}")
    t.iln("")


@bt.snapshot_httpx()
def test_introducing_predictive_application(t: bt.TestCaseRun):
    """Run predict_hn on a handful of phrasings of the same idea.

    The point: same concept, different framings — does Aito move?
    These are the "would-this-launch-work" titles a marketer would
    actually consider.
    """
    c = _client()

    t.h1("Predicting performance of 'Introducing Predictive Application'")
    t.tln(
        "Same concept, six framings. Aito should rate Show HN higher than "
        "the bare 'Introducing X' headline — Show HN posts get a bit more "
        "engagement on average; Ask HN posts get comments but rarely upvotes."
    )
    t.tln("")

    variants = [
        "Introducing Predictive Application",
        "Show HN: Introducing Predictive Application",
        "Predictive Application: a database that predicts answers",
        "Ask HN: How would a predictive application change your workflow?",
        "Predictive Application beats GPT-5 at structured prediction",
        "Why we built Predictive Application instead of training a model",
    ]

    for title in variants:
        req = PredictRequest(title=title)
        res = predict_hn(c, req)
        _print_prediction(t, title, res)

    t.tln("")
    t.assertln(
        "all six predictions returned a valid bucket distribution",
        True,
    )


@bt.snapshot_httpx()
def test_introducing_predictive_application_metadata(t: bt.TestCaseRun):
    """Same title, varying posting metadata. Surfaces whether time-of-day
    / day-of-week / domain materially shift the prediction on our corpus
    (with only 9.5k rows the answer is "barely" — we still book it)."""
    c = _client()

    t.h1("'Show HN: Introducing Predictive Application' across postings")
    t.tln("")

    title = "Show HN: Introducing Predictive Application"

    metas = [
        {},  # bare
        {"domain": "github.com"},
        {"domain": "aito.ai"},
        {"hour_utc": 14, "day_of_week": 1},   # Tue 14:00 UTC — the classic window
        {"hour_utc": 3, "day_of_week": 5},    # Sat 03:00 — the graveyard
        {"domain": "aito.ai", "hour_utc": 14, "day_of_week": 1},
    ]

    for meta in metas:
        req = PredictRequest(title=title, **meta)
        res = predict_hn(c, req)
        label = ", ".join(f"{k}={v}" for k, v in meta.items()) or "(no metadata)"
        t.h2(label)
        t.iln(
            f"front page: {res.headline['front_page_pct']:.1f}%  |  "
            f"likely ~{round(res.estimated_score.most_likely_midpoint)} pts  |  "
            f"likely ~{res.estimated_comments:.0f} comments"
        )
        t.iln("")
