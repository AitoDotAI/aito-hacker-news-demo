"use client";

import { useEffect, useRef, useState } from "react";
import { onAitoLatency, type AitoLatencySample } from "@/lib/api";

const WINDOW = 30;

function fmtMs(ms: number): string {
  if (ms < 10) return ms.toFixed(1) + "ms";
  if (ms < 1000) return Math.round(ms) + "ms";
  return (ms / 1000).toFixed(2) + "s";
}

function p(samples: number[], pct: number): number {
  if (samples.length === 0) return 0;
  const sorted = [...samples].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * pct));
  return sorted[idx];
}

/**
 * Topbar pill showing live Aito round-trip latency. Subscribes to
 * X-Aito-Ms response headers via apiFetch; keeps a rolling window
 * of the last N calls. Hovering reveals min/p50/p95 across the
 * window, plus the most recent paths.
 */
export default function LatencyBadge() {
  const [samples, setSamples] = useState<AitoLatencySample[]>([]);
  const [hover, setHover] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    return onAitoLatency((s) => {
      setSamples((prev) => {
        const next = [...prev, s];
        if (next.length > WINDOW) next.splice(0, next.length - WINDOW);
        return next;
      });
    });
  }, []);

  if (samples.length === 0) {
    return null;
  }

  const last = samples[samples.length - 1];
  const msList = samples.map((s) => s.ms);
  const avg = msList.reduce((a, b) => a + b, 0) / msList.length;
  const p50 = p(msList, 0.5);
  const p95 = p(msList, 0.95);
  const min = Math.min(...msList);

  return (
    <span
      ref={ref}
      className="latency-badge"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 9px",
        borderRadius: 12,
        border: "1px solid #a8d8b0",
        background: "var(--green-bg)",
        color: "var(--green)",
        fontSize: 11,
        fontWeight: 600,
        fontFamily: "'IBM Plex Mono', monospace",
        cursor: "default",
        position: "relative",
      }}
      title="Live Aito round-trip latency"
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: "#6ab87a",
          boxShadow: "0 0 4px #6ab87a",
        }}
      />
      <span>aito {fmtMs(last.ms)}</span>
      {hover && (
        <span
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            right: 0,
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "10px 12px",
            boxShadow: "0 4px 12px rgba(0,0,0,.1)",
            zIndex: 1000,
            minWidth: 220,
            color: "var(--text)",
            fontFamily: "'IBM Plex Sans', sans-serif",
            fontWeight: 400,
          }}
        >
          <div style={{ fontSize: 10, fontWeight: 600, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".5px", marginBottom: 6 }}>
            Last {samples.length} Aito calls
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "3px 12px", fontSize: 11.5 }}>
            <span style={{ color: "var(--text3)" }}>min</span>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{fmtMs(min)}</span>
            <span style={{ color: "var(--text3)" }}>p50</span>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{fmtMs(p50)}</span>
            <span style={{ color: "var(--text3)" }}>p95</span>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{fmtMs(p95)}</span>
            <span style={{ color: "var(--text3)" }}>avg</span>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>{fmtMs(avg)}</span>
            <span style={{ color: "var(--text3)" }}>last</span>
            <span style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
              {fmtMs(last.ms)}
              {last.calls > 1 && (
                <span style={{ color: "var(--text3)", marginLeft: 6 }}>
                  ({last.calls} calls)
                </span>
              )}
            </span>
          </div>
          <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--border2)", fontSize: 10, color: "var(--text3)", lineHeight: 1.5 }}>
            Round-trip ms server→Aito→server, summed across all
            Aito calls in the request. Excludes Next.js render and
            wire transit.
          </div>
        </span>
      )}
    </span>
  );
}
