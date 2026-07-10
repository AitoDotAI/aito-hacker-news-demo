"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import WhyCards from "./WhyCards";
import type { WhyFactor } from "@/lib/types";

interface WhyTooltipProps {
  label: string;
  factors: WhyFactor[];
  /** Top prediction's $p — drives the calculation summary in WhyCards. */
  confidence?: number;
}

export default function WhyTooltip({ label, factors, confidence = 0 }: WhyTooltipProps) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  const updatePosition = useCallback(() => {
    if (!btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    // Popup is 380px wide and positioned with translate(-50%, -100%).
    // Clamp the anchor so the popup never escapes the viewport, even
    // when the trigger button sits near the right edge of a narrow column.
    const popupWidth = 380;
    const margin = 12;
    const half = popupWidth / 2;
    const anchorX = rect.left + rect.width / 2;
    const minX = half + margin;
    const maxX = window.innerWidth - half - margin;
    const clampedX = Math.max(minX, Math.min(maxX, anchorX));
    setPos({
      top: rect.top - 8,
      left: clampedX,
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    function handleClick(e: MouseEvent) {
      if (
        popupRef.current && !popupRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open, updatePosition]);

  if (!factors || factors.length === 0) return null;

  return (
    <>
      <button
        ref={btnRef}
        className="why-btn"
        onClick={() => setOpen(!open)}
        title="Why this prediction?"
      >
        ?
      </button>
      {open && pos && createPortal(
        <div
          ref={popupRef}
          className="why-popup"
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            transform: "translate(-50%, -100%)",
            // Wider than the legacy flat-list popup -- pattern cards
            // need horizontal room for the highlighted text spans.
            width: 380,
          }}
        >
          <div className="why-title">Why {label}?</div>
          <WhyCards why={factors} confidence={confidence} />
          <div className="why-footer" style={{ marginTop: 8 }}>
            Lift {">"} 1 means this feature makes the prediction more likely; base P is the prior probability of the predicted value.
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
