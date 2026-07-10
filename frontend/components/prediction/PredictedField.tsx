"use client";

import { useState } from "react";
import WhyTooltip from "./WhyTooltip";

interface PredictedFieldProps {
  label: string;
  fieldName: string;
  value: string;
  predicted: boolean;
  confidence?: number;
  whyFactors?: { field: string; value: string; lift: number }[];
  highlightedFields?: Set<string>;
  onChange: (fieldName: string, value: string) => void;
  readOnly?: boolean;
}

/**
 * Three-state field:
 *  - empty: no value, no prediction yet
 *  - predicted: italic + dimmed + gold tint, "Predicted" badge, confirms on Tab/blur
 *  - user: solid styling, optional check icon, edits are user-entered
 */
export default function PredictedField({
  label,
  fieldName,
  value,
  predicted,
  confidence,
  whyFactors,
  highlightedFields,
  onChange,
  readOnly,
}: PredictedFieldProps) {
  const [confirmed, setConfirmed] = useState(false);
  const isHighlighted = highlightedFields?.has(fieldName);
  const isEmpty = !value;
  const isPredicted = predicted && !confirmed;
  const isUser = !isEmpty && !isPredicted;

  const inputClass = [
    "field-input",
    isPredicted ? "predicted" : "",
    isHighlighted ? "highlighted" : "",
  ].filter(Boolean).join(" ");

  const handleBlur = () => {
    // Tab/click-away on a predicted field promotes it to user-confirmed
    if (predicted && value) setConfirmed(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape" && predicted) {
      onChange(fieldName, "");
      setConfirmed(false);
    }
  };

  return (
    <div className="field-group">
      <div className="field-label">{label}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <input
          className={inputClass}
          value={value}
          onChange={(e) => { setConfirmed(true); onChange(fieldName, e.target.value); }}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          readOnly={readOnly}
          placeholder={isPredicted ? "" : label.toLowerCase()}
        />
        {isPredicted && whyFactors && whyFactors.length > 0 && (
          <WhyTooltip label={value} factors={whyFactors} confidence={confidence} />
        )}
      </div>
      {isPredicted && confidence != null && (
        <div className="field-predicted-label">
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2 5l2 2 4-4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          Predicted &middot; {(confidence * 100).toFixed(1)}% &middot; tab to confirm, esc to clear
        </div>
      )}
      {isUser && !isEmpty && (
        <div style={{ fontSize: 10, color: "var(--green)", marginTop: 2, display: "flex", alignItems: "center", gap: 4 }}>
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2 5l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          Confirmed
        </div>
      )}
    </div>
  );
}
