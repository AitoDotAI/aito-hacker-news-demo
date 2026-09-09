"""Turn an evaluation report into calibration anchors for src/calibration.py.

`scripts/evaluate.py` records, for each band of predicted probability, how
often those submissions actually reached the front page. That pairing is
the calibration curve — this script turns it into the constant that
src/calibration.py ships, so the mapping is always traceable to a
measurement rather than hand-tuned.

Monotonicity matters: a calibration map that dips would mean a *higher*
raw prediction produced a *lower* corrected one, which is incoherent. Bins
usually come out monotone; when noise makes them dip, pool-adjacent-
violators merges the offenders (the standard isotonic-regression step)
rather than us silently reordering them.

Usage:
    uv run python -m scripts.fit_calibration data/eval-report-v2.json
    uv run python -m scripts.fit_calibration data/eval-report-v2.json --min-n 20

Prints a ready-to-paste CALIBRATION_ANCHORS block plus the BASE_RATE.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Bins thinner than this are too noisy to anchor a curve on — the top bin
# of a typical run holds a handful of submissions.
DEFAULT_MIN_N = 10


def pool_adjacent_violators(points: list[tuple[float, float, int]]
                            ) -> list[tuple[float, float]]:
    """Enforce a non-decreasing observed sequence by merging violators.

    Each point is (predicted, observed, n); merging averages the observed
    values weighted by n, which is what isotonic regression does.
    """
    stack: list[tuple[float, float, int]] = []
    for pred, obs, n in points:
        stack.append((pred, obs, n))
        # Merge backwards while the sequence dips.
        while len(stack) > 1 and stack[-2][1] > stack[-1][1]:
            p2, o2, n2 = stack.pop()
            p1, o1, n1 = stack.pop()
            merged_n = n1 + n2
            merged_obs = (o1 * n1 + o2 * n2) / merged_n
            # Keep the higher predicted value as the anchor's x, so the
            # merged segment still spans the range it came from.
            stack.append((max(p1, p2), merged_obs, merged_n))
    return [(p, o) for p, o, _ in stack]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("report", help="path to an eval report JSON")
    ap.add_argument("--min-n", type=int, default=DEFAULT_MIN_N,
                    help=f"drop calibration bins thinner than this "
                         f"(default {DEFAULT_MIN_N})")
    args = ap.parse_args(argv)

    path = Path(args.report)
    if not path.exists():
        ap.error(f"no such report: {path}")
    report = json.loads(path.read_text())

    bins = report["full_model"]["calibration"]
    kept = [b for b in bins if b["n"] >= args.min_n]
    dropped = [b for b in bins if b["n"] < args.min_n]

    if len(kept) < 2:
        ap.error(
            f"only {len(kept)} bins have n >= {args.min_n}; not enough to fit "
            f"a curve. Re-run evaluate.py with a larger --n."
        )

    points = [(b["mean_predicted"], b["observed"], b["n"]) for b in kept]
    anchors = pool_adjacent_violators(points)

    corpus = report["corpus"]
    holdout = report["holdout"]

    out = sys.stdout.write
    out("# Paste into src/calibration.py\n#\n")
    out(f"# Fitted from {path.name}\n")
    out(f"#   corpus  {corpus['rows']:,} rows, {corpus['oldest'][:10]} → "
        f"{corpus['newest'][:10]} (env: {corpus.get('env', 'master')})\n")
    out(f"#   holdout {holdout['n']:,} submissions, {holdout['start'][:10]} → "
        f"{holdout['end'][:10]}\n")
    out(f"#   base rate {holdout['base_rate']:.1%}, "
        f"AUC {report['full_model']['auc']:.3f}\n")
    if dropped:
        out(f"#   dropped {len(dropped)} bin(s) with n < {args.min_n}: "
            f"{', '.join(b['range'] for b in dropped)}\n")
    if len(anchors) < len(kept):
        out(f"#   pooled {len(kept) - len(anchors)} non-monotone bin(s)\n")
    out("\n")

    out("CALIBRATION_ANCHORS: list[tuple[float, float]] = [\n")
    out("    (0.000, 0.000),\n")
    for pred, obs in anchors:
        out(f"    ({pred:.3f}, {obs:.3f}),\n")
    out("]\n\n")
    out(f"BASE_RATE = {holdout['base_rate']:.3f}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
