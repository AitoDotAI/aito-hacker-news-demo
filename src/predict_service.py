"""The /api/predict-hn handler — orchestrates the Aito calls and shapes the
response for the frontend.

Fans out into three Aito calls per request:

  1. _predict on `success_bucket`  → 5-bucket probability distribution
                                      (the stacked bar in the UI)
  2. _predict on `front_page`      → binary headline number
                                      ("34% chance of front page")
  3. _search on title (similarity) → list of similar past submissions
                                      with their actual scores

Numeric expectations (estimated upvotes, estimated comments) are derived,
not separate Aito calls:

  - estimated_score    = Σ p(bucket) · midpoint(bucket)
                         (the brief explicitly recommends predicting
                          buckets over raw score because score is
                          log-distributed and noisy; we re-derive an
                          expected value here for the UI headline)
  - estimated_comments = mean(comments) over the top-K similar posts

That's a deliberate trade: we get a friendly point estimate without an
extra Aito round trip, and we communicate uncertainty by also showing the
full bucket distribution and the actual spread of similar posts.
"""

from __future__ import annotations

import math
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.aito_client import AitoClient
from src.calibration import (
    BASE_RATE,
    band as calibration_band,
    calibrate,
    relative_to_base,
)

TABLE = "hn_submissions"

BUCKET_ORDER: list[str] = ["flop", "low", "mid", "hit", "viral"]

BUCKET_LABELS: dict[str, str] = {
    "flop":  "Flop (<10)",
    "low":   "Low (10-49)",
    "mid":   "Mid (50-149)",
    "hit":   "Hit (150-499)",
    "viral": "Viral (500+)",
}

# Midpoints used for the expected-score computation. Score is power-law
# distributed on HN, so we pick midpoints that lean toward the lower end
# of each bucket — using the arithmetic midpoint of (150, 499) would
# overestimate, since hits cluster nearer 150 than 499.
BUCKET_MIDPOINTS: dict[str, float] = {
    "flop":  3.0,
    "low":   22.0,
    "mid":   85.0,
    "hit":   240.0,
    "viral": 900.0,
}

SIMILAR_LIMIT = 8
SIMILAR_FETCH = 200  # how many we ask Aito for before re-ranking client-side
# How many of the input's tokens go into the candidate search. Capped at
# the rarest few — see the comment in predict_hn().
SEARCH_TOKENS = 5

# Stop tokens we don't want to drive similarity:
#  - English stopwords ("the", "a") that Aito's analyzer mostly handles but
#    not exhaustively
#  - HN-specific decorators ("show", "hn", "ask") so search isn't dominated
#    by "every other Show HN post"
_STOP = {
    "a", "an", "the", "and", "or", "but", "of", "for", "to", "in", "on", "at",
    "is", "it", "this", "that", "with", "by", "from", "as", "be", "are", "was",
    "show", "hn", "ask", "tell",
}


def _tokenize(text: str) -> list[str]:
    """Lower-case alphanumeric tokens, length > 2, not stopwords."""
    return [
        t for t in re.findall(r"[A-Za-z0-9]+", text.lower())
        if len(t) > 2 and t not in _STOP
    ]


# ── Token rarity (IDF) ───────────────────────────────────────────────
#
# Plain token-overlap ranking treats every shared word alike, so "Why I
# Left Rust" retrieved "Why We're Bad at CSS" and "Why Git for Data?" —
# all matching on "why". Since the similar-posts list is the demo's main
# evidence, matching on the *rare* shared words is what makes it
# convincing.
#
# Document frequencies are a property of a fixed corpus, so we look each
# token up once and keep it. Steady state is nearly free: the common
# tokens that dominate ranking are exactly the ones that get cached first.

_DF_CACHE: dict[tuple[str, str], int] = {}
_CORPUS_SIZE: dict[str, int] = {}
_DF_LOCK = threading.Lock()

# Tokens we could not measure fall back to this weight — mid-range, so an
# unknown token neither dominates nor vanishes.
_DEFAULT_IDF = 3.0
_DF_WORKERS = 8


def _corpus_size(aito: AitoClient) -> int:
    key = aito.base_url
    cached = _CORPUS_SIZE.get(key)
    if cached is not None:
        return cached
    try:
        total = int(aito.search(table=TABLE, where={}, limit=0).get("total") or 0)
    except Exception:  # noqa: BLE001 — ranking must not break the prediction
        return 0
    with _DF_LOCK:
        _CORPUS_SIZE[key] = total
    return total


def _document_frequency(aito: AitoClient, token: str) -> int | None:
    """How many submissions contain `token` in their title. None on failure."""
    key = (aito.base_url, token)
    cached = _DF_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        r = aito.search(
            table=TABLE, where={"title": {"$match": token}}, limit=0,
        )
        df = int(r.get("total") or 0)
    except Exception:  # noqa: BLE001
        return None
    with _DF_LOCK:
        _DF_CACHE[key] = df
    return df


def _idf_weights(aito: AitoClient, tokens: list[str]) -> dict[str, float]:
    """{token → idf}. Uncached tokens are fetched concurrently so a cold
    cache costs one round trip rather than one per token."""
    n = _corpus_size(aito)
    if not n:
        return {t: _DEFAULT_IDF for t in tokens}

    missing = [t for t in tokens if (aito.base_url, t) not in _DF_CACHE]
    if missing:
        with ThreadPoolExecutor(max_workers=min(_DF_WORKERS, len(missing))) as ex:
            list(ex.map(lambda t: _document_frequency(aito, t), missing))

    weights: dict[str, float] = {}
    for t in tokens:
        df = _DF_CACHE.get((aito.base_url, t))
        if df is None:
            weights[t] = _DEFAULT_IDF
        else:
            # Smoothed IDF, floored at 0 so a token appearing in nearly
            # every row contributes nothing rather than going negative.
            weights[t] = max(0.0, math.log((n + 1) / (df + 1)))
    return weights


# ── Request / response models ────────────────────────────────────────

class PredictRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    domain: str | None = Field(default=None, max_length=120)
    hour_utc: int | None = Field(default=None, ge=0, le=23)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    # Override the derived title length to ask "what if the title were
    # N chars?" Omit (or pass None) to use the actual title length.
    title_length: int | None = Field(default=None, ge=1, le=500)
    # How many similar past submissions to surface. Defaults to 8.
    similar_limit: int | None = Field(default=None, ge=1, le=30)


class BucketProbability(BaseModel):
    bucket: str
    label: str
    probability: float
    # Top contributing $why factors for THIS bucket — pulled from the
    # per-hit $why in the single _predict response (Aito returns one
    # $why per predicted value, not one for the whole query). Lifts
    # below 0.7 / above 1.4 ish are the actual movers.
    why_factors: list["WhyFactor"] = []


class SimilarPost(BaseModel):
    title: str
    url: str | None
    domain: str
    score: int
    comments: int
    success_bucket: str
    created_at: str | None
    similarity: float | None = None


class WhyFactor(BaseModel):
    """A single $why explanation entry from Aito's predict response,
    normalised to {field, value, weight} for the UI."""
    field: str
    value: Any
    weight: float | None = None


class EstimatedScore(BaseModel):
    """Expected-value point estimate (Σ p · midpoint) plus the most-likely
    bucket midpoint. The expectation can sit well above the modal value when
    the distribution has a long viral tail — we expose both so the UI can
    show "most likely X, but the long tail puts the average at Y"."""
    expected: float
    most_likely_bucket: str
    most_likely_midpoint: float


class PredictResponse(BaseModel):
    input: PredictRequest
    derived: dict[str, Any]  # is_show_hn, is_ask_hn, title_length, etc.
    headline: dict[str, Any]  # { front_page_pct, label }
    bucket_distribution: list[BucketProbability]
    estimated_score: EstimatedScore
    estimated_comments: float
    similar_posts: list[SimilarPost]
    aito_calls: list[dict[str, Any]]  # for the AitoPanel — echo of what we ran


# ── Implementation ───────────────────────────────────────────────────

def _build_where(req: PredictRequest, derived: dict[str, Any]) -> dict[str, Any]:
    """Build the Aito `where` clause. Only include fields the user provided
    (or that we derived deterministically from the title); everything else
    is left out so Aito uses its priors.

    Continuous numeric fields (`title_length`, `hour_utc`) are wrapped in
    `$numeric` so Aito treats them as proximity-style features instead of
    exact-equality filters — a title of 47 chars should be informed by
    titles near that length, not only by other 47-char titles (of which
    there are usually a handful at most).

    `day_of_week` is left as a bare categorical: it's cyclical (Sun/Mon
    are conceptually adjacent but numerically far apart), so $numeric
    proximity would mislead.
    """
    where: dict[str, Any] = {"title": req.title}
    if req.domain:
        where["domain"] = req.domain.strip().lower()
    if req.hour_utc is not None:
        where["hour_utc"] = {"$numeric": req.hour_utc}
    if req.day_of_week is not None:
        where["day_of_week"] = req.day_of_week
    where["is_show_hn"] = derived["is_show_hn"]
    where["is_ask_hn"] = derived["is_ask_hn"]
    length_val = (
        req.title_length if req.title_length is not None else derived["title_length"]
    )
    where["title_length"] = {"$numeric": length_val}
    return where


def _derive(req: PredictRequest) -> dict[str, Any]:
    t = req.title
    return {
        "is_show_hn": t.startswith("Show HN:"),
        "is_ask_hn": t.startswith("Ask HN:"),
        "title_length": len(t),
    }


def _bucket_probabilities(predict_response: dict) -> dict[str, float]:
    """Extract a {bucket → probability} map from the Aito predict response.
    Missing buckets default to 0.0 (Aito returns whatever fits in `limit`)."""
    out = {b: 0.0 for b in BUCKET_ORDER}
    for hit in predict_response.get("hits", []):
        feature = hit.get("feature")
        if isinstance(feature, str) and feature in out:
            out[feature] = float(hit.get("$p", 0.0))
    return out


def _front_page_pct(predict_response: dict) -> float:
    """Pull the `true` probability out of a binary predict response."""
    for hit in predict_response.get("hits", []):
        # Aito returns booleans as JSON `true`/`false`
        if hit.get("feature") is True:
            return float(hit.get("$p", 0.0)) * 100.0
    return 0.0


def _similar_posts(
    search_response: dict,
    input_tokens: set[str],
    limit: int,
    idf: dict[str, float] | None = None,
) -> list[SimilarPost]:
    """Convert hits → SimilarPost, then re-rank against the input.

    Aito's $similarity collapses to a constant across $or hits, so ranking
    happens client-side. Shared tokens are weighted by IDF, so agreeing on
    "rust" counts for much more than agreeing on "why" — without it the
    list fills with posts that share only a filler word.
    """
    rows: list[tuple[float, SimilarPost]] = []
    for hit in search_response.get("hits", []):
        title = hit.get("title")
        if not title:
            continue
        title_tokens = set(_tokenize(title))
        if not title_tokens:
            continue
        shared = input_tokens & title_tokens
        if not shared:
            continue
        weight = sum((idf or {}).get(t, 1.0) for t in shared) if idf else len(shared)
        if weight <= 0:
            continue
        # Coordination: how much of the input this title actually covers.
        # Without it, one rare shared word outranks two topical ones —
        # "Is history written by the winners?" beat every Rust post for
        # the query "…Postgres client written in Rust", because "written"
        # happens to be rarer than "rust". Squared, so covering two of
        # three query words beats covering one decisively.
        coord = (len(shared) / len(input_tokens)) ** 2 if input_tokens else 0.0
        # Mildly penalise long titles that match by sheer coverage.
        rank = weight * coord / (len(title_tokens) ** 0.5)
        rows.append((
            rank,
            SimilarPost(
                title=title,
                url=hit.get("url") or None,
                domain=hit.get("domain") or "unknown",
                score=int(hit.get("score") or 0),
                comments=int(hit.get("comments") or 0),
                success_bucket=hit.get("success_bucket") or "flop",
                created_at=hit.get("created_at"),
                similarity=round(rank, 3),
            ),
        ))
    rows.sort(key=lambda r: -r[0])
    return [p for _, p in rows[:limit]]


def _expected_score(bucket_probs: dict[str, float]) -> EstimatedScore:
    expectation = sum(bucket_probs[b] * BUCKET_MIDPOINTS[b] for b in BUCKET_ORDER)
    modal = max(BUCKET_ORDER, key=lambda b: bucket_probs[b])
    return EstimatedScore(
        expected=expectation,
        most_likely_bucket=modal,
        most_likely_midpoint=BUCKET_MIDPOINTS[modal],
    )


def _expected_comments(similar: list[SimilarPost], bucket_probs: dict[str, float]) -> float:
    """Mean comments from the top similar posts, weighted toward the
    bucket-prob distribution if similar is sparse."""
    if similar:
        # Weight top-K similar posts; trim ties at the bottom.
        top = sorted(similar, key=lambda s: -(s.similarity or 0.0))[:5]
        return sum(s.comments for s in top) / len(top)
    # Fallback: a coarse map from expected bucket to comment count.
    fallback = {"flop": 1.0, "low": 5.0, "mid": 20.0, "hit": 60.0, "viral": 250.0}
    return sum(bucket_probs[b] * fallback[b] for b in BUCKET_ORDER)


def _normalize_why_for_hit(hit: dict, limit: int = 3) -> list[WhyFactor]:
    """Flatten one Aito predict hit's nested $why structure into a short
    list of UI-ready (field, value, lift) rows.

    Aito's $why for a categorical predict is a recursive tree:

        {type: "product", factors: [
          {type: "baseP", value: 0.86, proposition: {...}},
          {type: "product", factors: [
            {type: "normalizer", ...},
            {type: "normalizer", ...}
          ]},
          {type: "relatedPropositionLift",
           value: 0.99,
           proposition: {title: {$has: "client"}}},
          ...
        ]}

    Each `relatedPropositionLift` leaf is "this proposition multiplied the
    prediction's odds by `value`x." We keep only those, drop near-1.0 lifts
    (no contribution), and sort by |lift - 1| so the biggest movers — in
    either direction — come first. Caller passes `limit` to cap.
    """
    root = hit.get("$why") if isinstance(hit, dict) else None
    if not isinstance(root, dict):
        return []

    leaves: list[tuple[str, Any, float]] = []
    _walk_why(root, leaves)
    leaves.sort(key=lambda x: abs(x[2] - 1.0), reverse=True)

    out: list[WhyFactor] = []
    seen: set[tuple[str, str]] = set()
    for field, value, lift in leaves:
        key = (field, str(value))
        if key in seen:
            continue
        seen.add(key)
        out.append(WhyFactor(field=field, value=value, weight=lift))
        if len(out) >= limit:
            break
    return out


def _walk_why(node: Any, out: list[tuple[str, Any, float]]) -> None:
    if not isinstance(node, dict):
        return
    t = node.get("type")
    if t == "relatedPropositionLift":
        lift = float(node.get("value") or 0.0)
        # Drop trivial contributions — keeps the UI focused on real drivers.
        if abs(lift - 1.0) < 0.05:
            return
        prop = node.get("proposition") or {}
        for field, cond in _iter_propositions(prop):
            out.append((field, cond, lift))
    elif t in ("product", None):
        for f in node.get("factors") or []:
            _walk_why(f, out)


def _iter_propositions(prop: dict):
    """Yield (field, value) pairs from a $why proposition, flattening $and.
    Unwraps Aito's value envelopes (`$has`, `$numeric`) so the UI sees the
    raw token/number, not the operator wrapper we sent in `where`.
    """
    if not isinstance(prop, dict):
        return
    if "$and" in prop:
        for sub in prop["$and"]:
            yield from _iter_propositions(sub)
        return
    for field, cond in prop.items():
        if isinstance(cond, dict):
            if "$has" in cond:
                yield field, cond["$has"]
            elif "$numeric" in cond:
                # Aito returns these as floats even for Int columns; coerce.
                v = cond["$numeric"]
                try:
                    yield field, int(v) if float(v).is_integer() else v
                except (TypeError, ValueError):
                    yield field, v
            else:
                yield field, cond
        else:
            yield field, cond


def predict_hn(aito: AitoClient, req: PredictRequest) -> PredictResponse:
    derived = _derive(req)
    where = _build_where(req, derived)

    bucket_resp = aito.predict(
        table=TABLE,
        where=where,
        predict_field="success_bucket",
        limit=5,
        # Ask for $why on this one only — it powers the "what drove this"
        # panel. The front_page predict is just a number.
        select=["feature", "$p", "$why"],
    )
    fp_resp = aito.predict(
        table=TABLE,
        where=where,
        predict_field="front_page",
        limit=2,
    )
    # Similar past submissions: tokenise the title, search with $or across
    # tokens, then re-rank in Python.
    #
    # Why not Aito's $similarity orderBy? With $or across tokens Aito
    # returns the same similarity score for every hit (each only proves
    # the disjunction with one match), so we can't actually rank with it.
    #
    # Which tokens go into the $or matters more than it looks. Aito returns
    # an arbitrary `limit` slice of the matches, and a disjunction
    # containing a common word like "why" matches tens of thousands of
    # rows — so the slice we get back is close to random and the re-rank
    # has nothing good to choose from. Searching on the *rarest* tokens
    # gives a candidate pool that is already topical.
    tokens = _tokenize(req.title)
    sim_limit = req.similar_limit if req.similar_limit is not None else SIMILAR_LIMIT
    idf = _idf_weights(aito, tokens[:12]) if tokens else {}

    if tokens:
        ranked_tokens = sorted(
            tokens[:12], key=lambda t: idf.get(t, _DEFAULT_IDF), reverse=True
        )
        search_tokens = ranked_tokens[:SEARCH_TOKENS]
        # Over-fetch so the re-rank has headroom.
        fetch_n = min(SIMILAR_FETCH, max(sim_limit * 12, SIMILAR_FETCH))
        token_clauses = [{"title": {"$match": t}} for t in search_tokens]
        where_search: dict[str, Any] = (
            token_clauses[0] if len(token_clauses) == 1 else {"$or": token_clauses}
        )
        similar_resp = aito.search(
            table=TABLE,
            where=where_search,
            limit=fetch_n,
        )
    else:
        fetch_n = 0
        similar_resp = {"hits": []}

    bucket_probs = _bucket_probabilities(bucket_resp)
    bucket_factors = _per_bucket_why(bucket_resp)
    similar = _similar_posts(similar_resp, set(tokens), limit=sim_limit, idf=idf)
    front_page_pct = _front_page_pct(fp_resp)
    estimated_score = _expected_score(bucket_probs)
    estimated_comments = _expected_comments(similar, bucket_probs)

    calibrated = calibrate(front_page_pct / 100.0)

    return PredictResponse(
        input=req,
        derived=derived,
        headline={
            # `front_page_pct` stays the calibrated number, since that's
            # what any consumer should actually use. The raw Aito output
            # is kept alongside it so the UI (and the AitoPanel) can show
            # its work rather than quietly rewriting the model.
            "front_page_pct": round(calibrated * 100.0, 1),
            "raw_front_page_pct": round(front_page_pct, 1),
            "base_rate_pct": round(BASE_RATE * 100.0, 1),
            "relative_to_base": round(relative_to_base(calibrated), 2),
            "band": calibration_band(calibrated),
            "label": _label_for_front_page(calibrated * 100.0),
        },
        bucket_distribution=[
            BucketProbability(
                bucket=b,
                label=BUCKET_LABELS[b],
                probability=bucket_probs[b],
                why_factors=bucket_factors.get(b, []),
            )
            for b in BUCKET_ORDER
        ],
        estimated_score=estimated_score,
        estimated_comments=round(estimated_comments, 1),
        similar_posts=similar,
        aito_calls=[
            {"op": "_predict", "field": "success_bucket", "where_keys": list(where.keys())},
            {"op": "_predict", "field": "front_page", "where_keys": list(where.keys())},
            {"op": "_search", "fetched": fetch_n, "returned": sim_limit},
        ],
    )


def _per_bucket_why(predict_response: dict) -> dict[str, list[WhyFactor]]:
    """Build a {bucket → top factors} map from the per-hit $why entries.
    Aito returns one $why per predicted value (each hit), so a single
    _predict on success_bucket already gives us per-bucket explanations
    without any extra calls."""
    out: dict[str, list[WhyFactor]] = {}
    for hit in predict_response.get("hits") or []:
        feature = hit.get("feature")
        if not isinstance(feature, str):
            continue
        out[feature] = _normalize_why_for_hit(hit, limit=3)
    return out


def _label_for_front_page(pct: float) -> str:
    """Human label for the calibrated probability.

    Phrased relative to the base rate rather than in absolute terms.
    "Unlikely" is true of ~92% of all HN submissions, so saying it about
    a specific one carries no information; "better odds than most" does.
    """
    return calibration_band(pct / 100.0).capitalize()
