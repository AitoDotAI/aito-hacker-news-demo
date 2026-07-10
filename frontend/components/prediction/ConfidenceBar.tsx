import { confClass } from "@/lib/api";

export default function ConfidenceBar({ value }: { value: number }) {
  // Cap displayed confidence at 0.99: a true 1.00 makes the bar look
  // suspicious ("how can ML be 100% sure?"). Aito's _predict produces
  // p≈1 for cardinality-1 matches and our rule path uses 0.99
  // deterministically. Both round to 1.00 with toFixed(2). Capping at
  // 0.99 visually keeps the "predictive, not omniscient" frame without
  // touching the underlying probability used for routing decisions.
  const display = Math.min(value, 0.99);
  const pct = Math.round(display * 100);
  return (
    <div className="conf">
      <div className="conf-bar">
        <div className={`conf-fill ${confClass(display)}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="conf-val">{display.toFixed(2)}</span>
    </div>
  );
}
