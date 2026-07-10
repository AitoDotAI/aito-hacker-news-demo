// Shared types for the Aito demo framework — used by the prediction primitives
// and the AitoPanel. Add your demo-specific types in a separate file
// (e.g. lib/<domain>-types.ts) rather than mixing them in here.

/**
 * One alternative in a categorical prediction. Returned by Aito's `_predict`
 * with `$p` (probability) and an optional `$why` explanation.
 */
export interface Alternative {
  value: string;
  display: string;
  confidence: number;
  why?: WhyFactor[];
}

/**
 * Grouped `$why` factor returned by Aito's `_predict`:
 *  - type: "base"    → base_p (prior probability for target_value)
 *  - type: "pattern" → a single conjunction lift. Two parallel arrays:
 *      highlights[]   — Aito's per-field highlighted contexts (text fields)
 *      propositions[] — flattened {field, value} list (always populated)
 *    The renderer prefers highlights when present (they include the full
 *    context with <mark> tags around matched tokens) and falls back to
 *    propositions for fields without text highlights.
 */
export interface WhyFactor {
  type?: "base" | "pattern";
  lift?: number;
  base_p?: number;
  target_value?: string | null;
  propositions?: WhyProposition[];
  highlights?: WhyHighlight[];
  // Legacy flat shape from old precomputed JSON: field/value/lift at top level.
  field?: string;
  value?: string;
}

export interface WhyProposition {
  field: string;
  value: string;
}

/** Per-field text highlight from Aito with `<mark>...</mark>` in the context. */
export interface WhyHighlight {
  field: string;
  /** Full context string for this field, with matched tokens wrapped in `<mark>`. */
  html: string;
}

// ── AitoPanel (context/side pane) ──────────────────────────────────────────

/** One row in the AitoPanel's "stats" block — e.g. `{ value: "12,481", label: "rows in `submissions`" }`. */
export interface AitoPanelStat {
  value: string;
  label: string;
}

/**
 * Optional ordered narrative of which Aito calls produce which UI parts.
 * Surfaces inside the AitoPanel as a numbered flow.
 */
export interface AitoFlowStep {
  /** Step number shown in the tour badge */
  n: number;
  /** Short description: what does this Aito call produce on the page */
  produces: string;
  /** Aito API call summary, e.g. "_predict gl_code WHERE customer_id, vendor" */
  call: string;
}

/**
 * Full AitoPanel configuration for a single page/view. Build one per page
 * (or per route segment) and pass it to `<AitoPanel config={...} />`.
 */
export interface AitoPanelConfig {
  /** Headline shown at the top of the panel, e.g. "Predicting GL code". */
  operation: string;
  /** Stats block — DB facts that ground the demo in real data. */
  stats: AitoPanelStat[];
  /** One-paragraph narrative of what's happening. */
  description: string;
  /** The actual Aito query JSON shown verbatim in a code block. */
  query: string;
  /** Reference links — schema, source, blog post, etc. */
  links: { label: string; url: string }[];
  /** Optional ordered narrative of which Aito calls produce which UI parts. */
  flow_steps?: AitoFlowStep[];
}
