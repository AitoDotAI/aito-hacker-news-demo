"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import type { Alternative } from "@/lib/types";

interface PredictionBadgeProps {
  value: string;
  confidence: number;
  alternatives?: Alternative[];
  onSelect?: (alt: Alternative) => void;
}

export default function PredictionBadge({ value, confidence, alternatives, onSelect }: PredictionBadgeProps) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; minWidth: number } | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  const updatePosition = useCallback(() => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    setPos({
      top: rect.bottom + 4,
      left: rect.left,
      minWidth: Math.max(220, rect.width),
    });
  }, []);

  useEffect(() => {
    if (!open) return;
    updatePosition();
    function handleClick(e: MouseEvent) {
      if (
        popupRef.current && !popupRef.current.contains(e.target as Node) &&
        ref.current && !ref.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [open, updatePosition]);

  const hasAlts = alternatives && alternatives.length > 1;

  return (
    <div ref={ref} style={{ display: "inline-block" }}>
      <span
        className="pred-badge"
        onClick={() => hasAlts && setOpen(!open)}
        style={hasAlts ? {} : { cursor: "default" }}
      >
        {value}
        {hasAlts && <span style={{ fontSize: 9, opacity: 0.6 }}>{open ? "▴" : "▾"}</span>}
      </span>

      {open && alternatives && pos && createPortal(
        <div
          ref={popupRef}
          className="alternatives-dropdown"
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            minWidth: pos.minWidth,
            zIndex: 1000,
          }}
        >
          {alternatives.map((alt, i) => (
            <div
              key={i}
              className={`alt-item ${alt.value === value ? "selected" : ""}`}
              onClick={() => {
                onSelect?.(alt);
                setOpen(false);
              }}
            >
              <span>{alt.display || alt.value}</span>
              <span className="conf-val" style={{ fontSize: 11 }}>
                {(alt.confidence * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>,
        document.body,
      )}
    </div>
  );
}
