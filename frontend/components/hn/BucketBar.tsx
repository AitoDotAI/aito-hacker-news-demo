"use client";

import type { BucketProbability, SuccessBucket, WhyFactor } from "@/lib/hn-types";

/**
 * Per-bucket rows: label | proportional bar | % | top $why factors.
 *
 * Bars share a linear scale (max bucket = 100% width) so the eye sees
 * the actual distribution rather than a normalised view; small buckets
 * still get a 1px stub via min-width so factors can sit beside them.
 *
 * Each row's $why factors come from the corresponding hit's $why in
 * the single _predict call — Aito returns one $why per predicted
 * value, so the five rows here are five different explanations, not
 * the same explanation sliced five ways.
 */

const COLORS: Record<SuccessBucket, string> = {
  flop: "#828282",
  low: "#5a7a8a",
  mid: "#3a8a6b",
  hit: "#d49830",
  viral: "#ff6600",
};

function shortField(field: string): string {
  // The schema uses long-ish names; abbreviate in the inline display.
  switch (field) {
    case "is_show_hn": return "show_hn";
    case "is_ask_hn":  return "ask_hn";
    case "day_of_week": return "dow";
    case "hour_utc":   return "hr";
    default:           return field;
  }
}

function factorChip(f: WhyFactor, key: number): React.ReactNode {
  const lift = f.weight ?? 1;
  const positive = lift >= 1.0;
  const liftStr = lift >= 10 ? lift.toFixed(0) : lift.toFixed(1);
  const value =
    typeof f.value === "string"
      ? f.value
      : typeof f.value === "boolean"
      ? (f.value ? "true" : "false")
      : String(f.value);
  return (
    <span key={key} className={`hn-bucket-why ${positive ? "pos" : "neg"}`} title={`${f.field} = ${value}, lift ${lift.toFixed(2)}`}>
      <span className="hn-bucket-why-val">{value}</span>
      <span className="hn-bucket-why-lift">×{liftStr}</span>
      <span className="hn-bucket-why-field">{shortField(f.field)}</span>
    </span>
  );
}

interface Props {
  distribution: BucketProbability[];
}

export default function BucketBar({ distribution }: Props) {
  const maxP = Math.max(...distribution.map((b) => b.probability), 0.001);
  return (
    <ol className="hn-bucket-rows">
      {distribution.map((b) => {
        const width = (b.probability / maxP) * 100;
        return (
          <li key={b.bucket} className="hn-bucket-row">
            <span className="hn-bucket-label">{b.bucket}</span>
            <span className="hn-bucket-bar-cell">
              <span
                className="hn-bucket-bar-fill"
                style={{ width: `${width}%`, background: COLORS[b.bucket] }}
              />
            </span>
            <span className="hn-bucket-pct">
              {(b.probability * 100).toFixed(b.probability < 0.005 ? 2 : 1)}%
            </span>
            <span className="hn-bucket-whys">
              {b.why_factors.length === 0 ? (
                <span className="hn-bucket-why-empty">—</span>
              ) : (
                b.why_factors.map(factorChip)
              )}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
