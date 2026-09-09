"use client";

import LiftHint from "./LiftHint";
import type { WhyFactor } from "@/lib/types";

// ── $why factor cards ─────────────────────────────────────────────
//
// Mirrors aito-demo's InvoicingPage explanation layout:
// - "Base probability" card with the historical rate of the target
// - "Pattern match" cards showing "When <field> contains <highlighted-tokens>
//   and <field2> = <value>" with the lift multiplier per pattern
// - Calculation summary: 46% × 2.0 × ... = 99%
//
// Reused by:
// - InvoiceDetail's prediction tab (with onHoverFactor wired to the
//   left-side input panel for cross-highlight)
// - WhyTooltip popup (no onHoverFactor — popups don't have a sibling
//   panel to highlight)

export interface HoverHighlight {
  field: string | null;
  value: string | null;
}

export default function WhyCards({
  why,
  confidence,
  onHoverFactor,
}: {
  why: WhyFactor[];
  confidence: number;
  onHoverFactor?: (h: HoverHighlight) => void;
}) {
  const base = why.find((f) => f.type === "base");
  const patterns = why.filter((f) => f.type === "pattern");
  const legacy = why.filter((f) => !f.type && f.field);  // old precomputed JSON

  const baseP = base?.base_p ?? 0;
  const lifts = patterns.map((p) => p.lift ?? 1);
  const hover = onHoverFactor ?? (() => {});

  // The lifts are marginal per-pattern factors; Aito's posterior is NOT
  // their naive product. With weak evidence the product does land on the
  // model's probability, but once the evidence is strong it overshoots —
  // measured on a sibling demo: 35% × 1.5 × 2.9 × 1.7 × 1.8 = 434% for a
  // class whose actual $p is 98%. Printing "= 98%" there is an
  // arithmetically false equation, the same demo-effect class as
  // "0% × 0.7 = 58%".
  //
  // Surface the normalising constant as its own term so the chain
  // reconciles and stays checkable by eye, rather than softening the
  // equals sign. Mirrors the grocery demo (aito-demo InvoicingPage).
  // Derive it from the ROUNDED figures actually on screen, not the raw
  // ones — otherwise multiplying what the reader sees still misses the
  // stated result, which defeats the point of showing the term at all.
  const shownBase = Math.round(baseP * 100) / 100;
  const shownLifts = lifts.map((l) => Number(l.toFixed(1)));
  const chainProduct = shownLifts.reduce((acc, l) => acc * l, shownBase);
  const normalizer = chainProduct > 0 ? confidence / chainProduct : 1;
  const showNormalizer = Math.abs(normalizer - 1) > 0.1;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {base && (
        <div style={{
          background: "var(--surface2)", borderRadius: 4,
          padding: "8px 10px",
          display: "flex", justifyContent: "space-between", gap: 8,
        }}>
          <div>
            <div style={{ fontSize: 10, color: "var(--text3)", textTransform: "uppercase", letterSpacing: ".6px" }}>
              Base probability
            </div>
            <div style={{ fontSize: 11, color: "var(--text2)" }}>
              Historical rate for <strong>{base.target_value || "this value"}</strong>
            </div>
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>
            {(baseP * 100).toFixed(0)}%
          </div>
        </div>
      )}

      {patterns.map((f, i) => {
        const lift = f.lift ?? 1;
        const negative = lift < 1;
        // Render rule: each "row" inside a pattern card corresponds to
        // one input field. Source of truth:
        //   - highlights[] when Aito returned them (text fields with
        //     analyzer matches): show the full context with <mark>
        //     tokens already inserted by Aito.
        //   - propositions[] otherwise (categorical fields): show
        //     "field = value".
        // We dedupe propositions by field so multi-token text matches
        // (e.g. description $has "office" + description $has "supplies")
        // collapse into the single highlight Aito returned for the
        // description field.
        const highlightFields = new Set((f.highlights ?? []).map((h) => h.field));
        const propsByField = new Map<string, string>();
        for (const p of f.propositions ?? []) {
          if (highlightFields.has(p.field)) continue;
          if (!propsByField.has(p.field)) propsByField.set(p.field, p.value);
        }
        const rows: { field: string; render: () => React.ReactNode }[] = [
          ...(f.highlights ?? []).map((h) => ({
            field: h.field,
            render: () => <span dangerouslySetInnerHTML={{ __html: h.html }} />,
          })),
          ...Array.from(propsByField.entries()).map(([field, value]) => ({
            field,
            render: () => <strong>{value}</strong>,
          })),
        ];
        const firstField = rows[0]?.field ?? null;

        return (
          <div
            key={i}
            onMouseEnter={() => hover({ field: firstField, value: null })}
            onMouseLeave={() => hover({ field: null, value: null })}
            style={{
              background: negative ? "rgba(220, 53, 69, 0.06)" : "var(--gold-light)",
              borderLeft: `3px solid ${negative ? "var(--red)" : "var(--gold-dark)"}`,
              borderRadius: 4,
              padding: "8px 10px",
              display: "flex", justifyContent: "space-between", gap: 12,
              cursor: "default",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 10,
                color: negative ? "var(--red)" : "var(--gold-dark)",
                textTransform: "uppercase", letterSpacing: ".6px", fontWeight: 600,
              }}>
                {negative ? "Counter-evidence" : "Pattern match"}
              </div>
              <div style={{ fontSize: 11, color: "var(--text2)", lineHeight: 1.55, marginTop: 2 }}>
                {rows.length === 0 ? null : (
                  <>
                    When{" "}
                    {rows.map((r, ri) => {
                      const sep = ri === 0 ? "" : ri === rows.length - 1 ? " and " : ", ";
                      const fieldLabel = r.field.replace(/^invoice_id\./, "");
                      return (
                        <span key={ri}>
                          {sep}
                          <code style={{ fontFamily: "'IBM Plex Mono', monospace", color: "var(--text3)" }}>{fieldLabel}</code>
                          {" is "}
                          {r.render()}
                        </span>
                      );
                    })}
                  </>
                )}
              </div>
            </div>
            <LiftHint value={lift} prefix="× " />
          </div>
        );
      })}

      {/* Legacy flat factors (from old precomputed JSON) */}
      {legacy.map((f, i) => (
        <div
          key={`legacy-${i}`}
          onMouseEnter={() => hover({ field: f.field ?? null, value: f.value ?? null })}
          onMouseLeave={() => hover({ field: null, value: null })}
          style={{
            fontSize: 11, color: "var(--text2)", padding: "3px 4px",
            display: "flex", justifyContent: "space-between", gap: 8,
          }}
        >
          <span>
            <code style={{ fontFamily: "'IBM Plex Mono', monospace", color: "var(--text3)" }}>{f.field}</code>
            {" = "}<strong>{f.value}</strong>
          </span>
          <LiftHint value={f.lift ?? 1} prefix="" />
        </div>
      ))}

      {(base || lifts.length > 0) && (
        <div style={{
          marginTop: 2, padding: "8px 10px",
          background: "var(--surface)", borderRadius: 4,
          display: "flex", alignItems: "baseline", justifyContent: "center", flexWrap: "wrap",
          fontSize: 12, color: "var(--text2)", gap: 4,
          fontFamily: "'IBM Plex Mono', monospace",
        }}>
          <span>{(baseP * 100).toFixed(0)}%</span>
          {lifts.map((lift, i) => (
            <span key={i}> × {lift.toFixed(1)}</span>
          ))}
          {showNormalizer && (
            <span style={{ color: "var(--text3)" }}> × {normalizer.toFixed(2)}</span>
          )}
          <span style={{ color: "var(--text3)" }}> = </span>
          <span style={{ fontWeight: 700, color: "var(--gold-dark)" }}>{(confidence * 100).toFixed(0)}%</span>
          {showNormalizer && (
            <div style={{
              flexBasis: "100%", textAlign: "center", marginTop: 4,
              fontSize: 10, color: "var(--text3)", fontFamily: "inherit",
              lineHeight: 1.45,
            }}>
              <strong>× {normalizer.toFixed(2)}</strong>{" "}
              is Aito&apos;s
              normalising constant — evidence that overlaps is not counted
              twice, so the result is not the raw product of the lifts.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
