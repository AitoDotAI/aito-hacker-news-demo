"""Discover top features associated with each success_bucket using
Aito's `_relate` endpoint.

For every bucket value (flop / low / mid / hit / viral) we ask Aito:
"of the rows where success_bucket = X, which values of <field> are
disproportionately common?" — for the fields the user can intuit on
HN: title tokens, posting domains, hours, days.

The fan-out is 5 buckets × 4 fields = 20 _relate calls. Each is
independent and pure (corpus doesn't change between reloads), so we
cache the result in-process and re-use across requests.

`_relate` response shape (per hit):
    {
      "related":   { "<field>": {"$has": "<value>"} },
      "condition": { "success_bucket": {"$has": "viral"} },
      "lift":      19.9,
      "fs": { "f": 13, "fOnCondition": 3, "n": 9500, ... },
      "ps": { "p": 0.0014, "pOnCondition": 0.029, ... },
      "info": { "mi": 0.087, ... },
    }
"""

from __future__ import annotations

import threading
from typing import Any

from pydantic import BaseModel

from src.aito_client import AitoClient

TABLE = "hn_submissions"

BUCKETS: list[str] = ["flop", "low", "mid", "hit", "viral"]

BUCKET_LABELS: dict[str, str] = {
    "flop":  "Flop (<10)",
    "low":   "Low (10-49)",
    "mid":   "Mid (50-149)",
    "hit":   "Hit (150-499)",
    "viral": "Viral (500+)",
}

# Fields to relate against each bucket. Order is preserved in the
# response so the UI can render them as columns / sections consistently.
RELATE_FIELDS: list[tuple[str, str]] = [
    ("title",       "Title tokens"),
    ("domain",      "Domains"),
    ("hour_utc",    "Hour (UTC)"),
    ("day_of_week", "Day of week"),
]

# Filtering / sizing.
MIN_LIFT = 1.4         # < 1.4× is "not really telling us anything"
MIN_COUNT_ON_COND = 2  # don't surface a feature that hits the bucket once
TOP_N_PER_FIELD = 12   # cap each list


# ── Models ────────────────────────────────────────────────────────────

class FeatureHit(BaseModel):
    value: Any                # the field value (string for text, int for hours)
    lift: float               # how much more likely this value is in this bucket
    count_in_bucket: int      # rows where bucket matches AND field has this value
    count_total: int          # rows where field has this value (any bucket)
    p_in_bucket: float        # P(value | bucket)
    p_overall: float          # P(value)


class FieldFeatures(BaseModel):
    field: str
    label: str
    hits: list[FeatureHit]


class BucketFeatures(BaseModel):
    bucket: str
    label: str
    row_count: int                  # corpus-wide # of rows with this bucket
    fields: list[FieldFeatures]


class CategoryFeaturesResponse(BaseModel):
    table: str
    total_rows: int
    buckets: list[BucketFeatures]
    aito_calls: int                 # # of _relate calls executed (for the UI)


# ── Implementation ────────────────────────────────────────────────────

_cache: dict[str, CategoryFeaturesResponse] = {}
_cache_lock = threading.Lock()


def _extract_value(related: dict, field: str) -> Any:
    """Unwrap Aito's `{<field>: {$has: X}}` to just X."""
    if not isinstance(related, dict):
        return None
    inner = related.get(field)
    if isinstance(inner, dict) and "$has" in inner:
        return inner["$has"]
    return inner


def _coerce_value(value: Any, field: str) -> Any:
    """hour_utc / day_of_week are Int columns — Aito returns them as
    floats; convert to int so the UI renders cleanly."""
    if value is None:
        return None
    if field in ("hour_utc", "day_of_week"):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return value
    return value


def _hits_for(aito: AitoClient, bucket: str, field: str) -> tuple[list[FeatureHit], int]:
    """Run a single _relate, filter + normalise hits.

    Returns (filtered_hits, total_rows_for_bucket).
    """
    resp = aito.relate(
        table=TABLE,
        where={"success_bucket": bucket},
        relate_field=field,
        limit=60,  # over-fetch so we have headroom after the lift filter
    )
    raw_hits = resp.get("hits") or []

    out: list[FeatureHit] = []
    bucket_n = 0  # fs.fCondition — same across hits, take from any
    for hit in raw_hits:
        lift = float(hit.get("lift") or 0.0)
        fs = hit.get("fs") or {}
        ps = hit.get("ps") or {}
        f_on = int(fs.get("fOnCondition") or 0)
        f = int(fs.get("f") or 0)
        bucket_n = int(fs.get("fCondition") or bucket_n)

        if lift < MIN_LIFT:
            continue
        if f_on < MIN_COUNT_ON_COND:
            continue

        value = _coerce_value(_extract_value(hit.get("related"), field), field)
        if value is None:
            continue

        out.append(FeatureHit(
            value=value,
            lift=round(lift, 2),
            count_in_bucket=f_on,
            count_total=f,
            p_in_bucket=round(float(ps.get("pOnCondition") or 0.0), 4),
            p_overall=round(float(ps.get("p") or 0.0), 4),
        ))

    out.sort(key=lambda h: -h.lift)
    return out[:TOP_N_PER_FIELD], bucket_n


def _compute(aito: AitoClient) -> CategoryFeaturesResponse:
    bucket_blocks: list[BucketFeatures] = []
    total_rows = 0
    calls = 0
    for bucket in BUCKETS:
        field_blocks: list[FieldFeatures] = []
        bucket_n = 0
        for field, label in RELATE_FIELDS:
            hits, n = _hits_for(aito, bucket, field)
            calls += 1
            if n > 0:
                bucket_n = n
            field_blocks.append(FieldFeatures(field=field, label=label, hits=hits))
        total_rows = max(total_rows, bucket_n)  # any field's fCondition+fNotCondition
        bucket_blocks.append(BucketFeatures(
            bucket=bucket,
            label=BUCKET_LABELS[bucket],
            row_count=bucket_n,
            fields=field_blocks,
        ))

    # Recover the actual corpus size: any hit carries fs.n. If we have
    # at least one bucket with field_blocks[0] hits, use that.
    return CategoryFeaturesResponse(
        table=TABLE,
        total_rows=total_rows,
        buckets=bucket_blocks,
        aito_calls=calls,
    )


def category_features(aito: AitoClient, force: bool = False) -> CategoryFeaturesResponse:
    """Cached fan-out. The first call is the expensive one (~20 Aito
    calls); subsequent calls return the cached result instantly.

    Pass force=True to bypass the cache (e.g. after reloading the corpus).
    """
    key = TABLE
    with _cache_lock:
        if not force and key in _cache:
            return _cache[key]
    result = _compute(aito)
    with _cache_lock:
        _cache[key] = result
    return result
