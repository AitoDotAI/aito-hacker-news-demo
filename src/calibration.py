"""Map Aito's raw front-page probability onto what we actually observed.

Aito's `_predict` returns a probability conditioned on the corpus. That
number is not wrong, but it is not a calibrated forecast about *today's*
Hacker News either: run `scripts/evaluate.py` and the raw output comes
back systematically overconfident above ~20% and slightly underconfident
at the bottom.

Rather than print the raw number and hope, we pin it to measured
out-of-sample frequencies and — more importantly — refuse to report more
precision than the measurement supports.

Provenance
----------
The anchors below are the calibration bins from a 900-submission holdout
(`data/eval-report.json`, corpus 2023-05-25 → 2024-01-12, holdout
2024-01-19 → 2026-08-01, base rate 7.6%):

    raw predicted     observed
         2.9%           5.7%
         7.3%           6.6%
        13.5%           8.1%
        24.4%          13.8%
        41.8%          28.6%

The mapping is monotone as measured, so simple piecewise-linear
interpolation is enough — no isotonic pooling was needed.

Caveat, stated because the UI states it too: these anchors are fit on the
same holdout the README reports AUC from, and the top bin rests on 7
submissions. The mapping is a correction of the obvious bias, not a
precision instrument. Regenerate it with `scripts/evaluate.py` whenever
the corpus is reloaded.
"""

from __future__ import annotations

from typing import Literal

# (raw probability, observed frequency) anchors. Must stay sorted by raw.
CALIBRATION_ANCHORS: list[tuple[float, float]] = [
    (0.000, 0.000),
    (0.029, 0.057),
    (0.073, 0.066),
    (0.135, 0.081),
    (0.244, 0.138),
    (0.418, 0.286),
]

# Above the highest anchor we have almost no measurements, so we stop
# interpolating and extrapolate along the last measured slope instead of
# letting the raw number run away to 80%+.
_TAIL_SLOPE = (
    (CALIBRATION_ANCHORS[-1][1] - CALIBRATION_ANCHORS[-2][1])
    / (CALIBRATION_ANCHORS[-1][0] - CALIBRATION_ANCHORS[-2][0])
)

# The base rate of the holdout — what you'd predict knowing nothing.
# The UI compares against this, because "12%" means nothing on its own
# but "1.6x the typical submission" does.
BASE_RATE = 0.076

Band = Literal["well below average", "below average", "about average",
               "above average", "well above average"]

# Band edges expressed as multiples of BASE_RATE. Chosen to be coarser
# than the measurement error: the evaluation resolves roughly a 2x
# difference between top and bottom decile, so five bands across that
# range is already at the limit of what the data supports.
_BAND_EDGES: list[tuple[float, Band]] = [
    (0.55, "well below average"),
    (0.85, "below average"),
    (1.20, "about average"),
    (1.90, "above average"),
]


def calibrate(raw_p: float) -> float:
    """Raw Aito probability → calibrated probability, both in [0, 1]."""
    if raw_p <= 0.0:
        return 0.0
    lo_raw, lo_obs = CALIBRATION_ANCHORS[0]
    for hi_raw, hi_obs in CALIBRATION_ANCHORS[1:]:
        if raw_p <= hi_raw:
            span = hi_raw - lo_raw
            if span <= 0:
                return hi_obs
            t = (raw_p - lo_raw) / span
            return lo_obs + t * (hi_obs - lo_obs)
        lo_raw, lo_obs = hi_raw, hi_obs
    # Past the last anchor: extend the final measured slope, capped well
    # short of certainty. We have never observed this demo be right about
    # a high-confidence prediction often enough to justify more.
    return min(0.60, lo_obs + (raw_p - lo_raw) * _TAIL_SLOPE)


def band(calibrated_p: float) -> Band:
    """Coarse verdict relative to the base rate.

    This is what the UI leads with. A single percentage implies a
    precision the holdout does not support; a band does not.
    """
    ratio = calibrated_p / BASE_RATE if BASE_RATE else 0.0
    for edge, name in _BAND_EDGES:
        if ratio < edge:
            return name
    return "well above average"


def relative_to_base(calibrated_p: float) -> float:
    """How many times the typical submission's odds. 1.0 = average."""
    return calibrated_p / BASE_RATE if BASE_RATE else 0.0
