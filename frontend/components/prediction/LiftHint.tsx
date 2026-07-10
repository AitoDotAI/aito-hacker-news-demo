"use client";

interface LiftHintProps {
  /** Multiplier value, e.g. 38 means "38×" */
  value: number;
  /** Optional prefix text, default "lift " */
  prefix?: string;
}

/**
 * Render a lift number with an explanatory tooltip. Lift = how many
 * times more often this combination occurs vs random expectation.
 * < 1 = anti-correlated, 1 = no signal, 5+ = strong, 20+ = very strong.
 */
export default function LiftHint({ value, prefix = "lift " }: LiftHintProps) {
  if (value == null || isNaN(value)) return null;
  const tone =
    value >= 20 ? "strong" :
    value >= 5 ? "good" :
    value >= 1 ? "weak" :
    "none";
  const color =
    tone === "strong" ? "var(--green)" :
    tone === "good" ? "var(--gold-dark)" :
    tone === "weak" ? "var(--text3)" :
    "var(--red)";
  const tooltip =
    `Lift = how many times more often this combination occurs than random.\n` +
    `> 20× very strong · 5–20× strong · 1–5× weak · < 1× anti-correlated.\n` +
    `This is ${value.toFixed(1)}× — ${tone}.`;
  return (
    <span title={tooltip} style={{ color, fontWeight: 600, cursor: "help", borderBottom: "1px dotted currentColor" }}>
      {prefix}{value.toFixed(1)}×
    </span>
  );
}
