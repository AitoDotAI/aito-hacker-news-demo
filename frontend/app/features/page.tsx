"use client";

import { useEffect, useState } from "react";
import HnTopBar from "@/components/hn/HnTopBar";
import Nav, { type NavRoute } from "@/components/shell/Nav";
import AitoPanel from "@/components/shell/AitoPanel";
import ErrorState from "@/components/shell/ErrorState";
import { apiFetch, ApiError } from "@/lib/api";
import type { AitoPanelConfig } from "@/lib/types";
import type {
  CategoryFeaturesResponse,
  FeatureHit,
  FieldFeatures,
  SuccessBucket,
} from "@/lib/hn-types";
import { DAYS } from "@/lib/hn-types";

const PANEL_CONFIG: AitoPanelConfig = {
  operation: "POST /api/v1/_relate × 20",
  stats: [
    { value: "5", label: "buckets" },
    { value: "4", label: "fields / bucket" },
    { value: "20", label: "Aito _relate calls" },
  ],
  description:
    "For each <code>success_bucket</code> value, we ask Aito's <code>_relate</code>: which values of " +
    "<code>title</code>, <code>domain</code>, <code>hour_utc</code>, <code>day_of_week</code> are disproportionately " +
    "common? Aito returns lift, counts, and mutual information per related value. We filter by lift × 1.4+ " +
    "and ≥ 2 hits in the bucket, then sort by lift.",
  query: JSON.stringify(
    {
      method: "POST",
      path: "/api/v1/_relate",
      body: {
        from: "hn_submissions",
        where: { success_bucket: "viral" },
        relate: "title",
        limit: 60,
      },
    },
    null,
    2,
  ),
  links: [
    { label: "View schema", url: "/api/schema" },
    { label: "_relate docs", url: "https://aito.ai/docs/api/" },
  ],
};

const ROUTES: NavRoute[] = [];

const BUCKET_COLORS: Record<SuccessBucket, string> = {
  flop: "#828282",
  low: "#5a7a8a",
  mid: "#3a8a6b",
  hit: "#d49830",
  viral: "#ff6600",
};

function formatValue(field: string, raw: string | number): string {
  if (field === "hour_utc") return `${String(raw).padStart(2, "0")}:00 UTC`;
  if (field === "day_of_week") {
    const n = typeof raw === "string" ? parseInt(raw, 10) : raw;
    return DAYS[n] ?? String(raw);
  }
  return String(raw);
}

function FieldList({ field, accent }: { field: FieldFeatures; accent: string }) {
  if (!field.hits.length) {
    return (
      <div className="hn-feat-field">
        <div className="hn-feat-field-label">{field.label}</div>
        <div className="hn-feat-empty">— no significant features</div>
      </div>
    );
  }
  return (
    <div className="hn-feat-field">
      <div className="hn-feat-field-label">{field.label}</div>
      <ol className="hn-feat-list">
        {field.hits.map((h: FeatureHit, i: number) => (
          <li key={i} className="hn-feat-row">
            <span className="hn-feat-value">{formatValue(field.field, h.value)}</span>
            <span className="hn-feat-lift" style={{ color: accent }}>
              ×{h.lift.toFixed(1)}
            </span>
            <span className="hn-feat-count">n={h.count_in_bucket}/{h.count_total}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function FeaturesPage() {
  const [data, setData] = useState<CategoryFeaturesResponse | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastResponseMs, setLastResponseMs] = useState<number | null>(null);
  const [lastQuery, setLastQuery] = useState<object | null>(null);

  useEffect(() => {
    const t0 = performance.now();
    setLastQuery({
      method: "POST",
      path: "/api/v1/_relate",
      body: { from: "hn_submissions", where: { success_bucket: "<bucket>" }, relate: "<field>" },
    });
    apiFetch<CategoryFeaturesResponse>("/api/category-features")
      .then((res) => {
        setLastResponseMs(Math.round(performance.now() - t0));
        setData(res);
      })
      .catch((e) => setError(e as Error))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="app">
      <Nav routes={ROUTES} />
      <main className="main">
        <HnTopBar subtitle="top features per bucket, via _relate" />
        <div className="content hn-content">
          <section className="hn-feat-intro">
            <div className="hn-block-title">top features per bucket</div>
            <div className="hn-meta-line">
              For each outcome bucket, Aito's <code>_relate</code> tells us which title tokens, domains,
              hours, and days are disproportionately associated with that bucket. Lift = how much more
              likely the feature is in this bucket vs. the corpus average. Tokens are stemmed by the
              English analyzer (so "franc" = France / franc, "illeg" = illegal / illegality).
            </div>
            {data && (
              <div className="hn-meta-line" style={{ marginTop: 4 }}>
                Computed from {data.total_rows.toLocaleString()} stories via {data.aito_calls}{" "}
                <code>_relate</code> calls. Subsequent loads are cached.
              </div>
            )}
          </section>

          {loading && (
            <div className="hn-feat-loading">Computing relations… (first load fans out to ~20 Aito calls)</div>
          )}

          {error && <ErrorState error={error} />}

          {data && (
            <div className="hn-feat-buckets">
              {data.buckets.map((b) => (
                <section key={b.bucket} className="hn-feat-bucket">
                  <header
                    className="hn-feat-bucket-head"
                    style={{ borderLeft: `4px solid ${BUCKET_COLORS[b.bucket]}` }}
                  >
                    <span className="hn-feat-bucket-name">{b.label}</span>
                    <span className="hn-meta-line">
                      n = {b.row_count.toLocaleString()} stories
                    </span>
                  </header>
                  <div className="hn-feat-grid">
                    {b.fields.map((fld) => (
                      <FieldList
                        key={fld.field}
                        field={fld}
                        accent={BUCKET_COLORS[b.bucket]}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}

          <div className="hn-footnote">
            <a href="/">← back to predict</a>
            {" | "}
            {lastResponseMs ?? "—"} ms · powered by{" "}
            <a href="https://aito.ai" target="_blank" rel="noopener noreferrer">
              Aito _relate
            </a>
          </div>
        </div>
      </main>
      <AitoPanel
        config={PANEL_CONFIG}
        lastQuery={lastQuery}
        lastResponseMs={lastResponseMs}
      />
    </div>
  );
}
