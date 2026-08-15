"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import HnTopBar from "@/components/hn/HnTopBar";
import Nav, { type NavRoute } from "@/components/shell/Nav";
import AitoPanel from "@/components/shell/AitoPanel";
import ErrorState from "@/components/shell/ErrorState";
import BucketBar from "@/components/hn/BucketBar";
import SimilarPosts from "@/components/hn/SimilarPosts";
import SimilarDistribution from "@/components/hn/SimilarDistribution";
import { apiFetch, ApiError } from "@/lib/api";
import type { AitoPanelConfig } from "@/lib/types";
import {
  DAYS,
  EXAMPLE_TITLES,
  type PredictHnInput,
  type PredictHnResponse,
} from "@/lib/hn-types";

const PANEL_CONFIG: AitoPanelConfig = {
  operation: "POST /api/v1/_predict + /_search",
  stats: [
    { value: "200k", label: "submissions indexed" },
    { value: "3", label: "Aito calls / prediction" },
    { value: "0", label: "ML pipelines" },
  ],
  description:
    "Each prediction fans out to three Aito calls: <code>_predict success_bucket</code> for the 5-class distribution, " +
    "<code>_predict front_page</code> for the binary headline, and <code>_search</code> for similar past submissions. " +
    "The search runs on the input's <em>rarest</em> tokens and the hits are re-ranked by IDF weight — matching on " +
    "&ldquo;rust&rdquo; should count for more than matching on &ldquo;why&rdquo;. Token rarity comes from cached " +
    "<code>_search</code> counts, so a cold token costs one extra call and nothing thereafter. " +
    "No training step and no model file — Aito infers directly from its index. The front-page number is " +
    "calibrated against a 900-submission holdout, because the raw output runs optimistic above 20%; both are shown.",
  query: JSON.stringify(
    {
      method: "POST",
      path: "/api/v1/_predict",
      body: {
        from: "hn_submissions",
        where: { title: "...", is_show_hn: false },
        predict: "success_bucket",
      },
    },
    null,
    2,
  ),
  links: [
    { label: "View schema", url: "/api/schema" },
    { label: "Aito docs", url: "https://aito.ai/docs/" },
  ],
};

const ROUTES: NavRoute[] = [];

function todayIsoUtc(): string {
  const d = new Date();
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(d.getUTCDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function dowFromIso(iso: string): number {
  // ISO yyyy-mm-dd → schema's 0=Mon..6=Sun. Falls back to today on
  // malformed input (browsers should already guard against this).
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return new Date().getUTCDay();
  const jsDow = new Date(Date.UTC(y, m - 1, d)).getUTCDay(); // 0=Sun..6=Sat
  return (jsDow + 6) % 7;
}

function nowDefaults() {
  const d = new Date();
  return {
    date: todayIsoUtc(),
    hour_utc: d.getUTCHours(),
    day_of_week: (d.getUTCDay() + 6) % 7,
  };
}

function domainFromTitle(title: string): string {
  if (title.startsWith("Ask HN:") || title.startsWith("Show HN:")) return "self";
  return "draft";
}

function fmtClock(iso: string, h: number): string {
  const dow = dowFromIso(iso);
  return `${DAYS[dow]} ${iso} ${h.toString().padStart(2, "0")}:00 UTC`;
}

export default function Home() {
  const defaults = useMemo(nowDefaults, []);

  const [title, setTitle] = useState("");
  const [domain, setDomain] = useState("");
  const [hourUtc, setHourUtc] = useState<number>(defaults.hour_utc);
  const [dateStr, setDateStr] = useState<string>(defaults.date);
  const [pinTime, setPinTime] = useState(false);
  // title_length: when not pinned, follows len(title.trim()) live. When
  // pinned, the user can override to ask "what if the title were N chars?"
  const [titleLength, setTitleLength] = useState<number>(0);
  const [pinLength, setPinLength] = useState(false);
  const [similarLimit, setSimilarLimit] = useState<number>(8);

  const derivedLength = title.trim().length;
  const effectiveLength = pinLength ? titleLength : derivedLength || 1;

  const [data, setData] = useState<PredictHnResponse | null>(null);
  const [error, setError] = useState<Error | ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastResponseMs, setLastResponseMs] = useState<number | null>(null);
  const [lastQuery, setLastQuery] = useState<object | null>(null);
  const titleRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { titleRef.current?.focus(); }, []);

  const onSubmit = useCallback(async () => {
    const trimmed = title.trim();
    if (!trimmed) { titleRef.current?.focus(); return; }
    setError(null);
    setLoading(true);
    const usedDate = pinTime ? dateStr : defaults.date;
    const body: PredictHnInput = {
      title: trimmed,
      domain: domain.trim() || null,
      hour_utc: pinTime ? hourUtc : defaults.hour_utc,
      day_of_week: dowFromIso(usedDate),
      // Always send title_length so it acts as a real inference feature
      // (override if user pinned, otherwise the actual length).
      title_length: pinLength ? titleLength : trimmed.length,
      similar_limit: similarLimit,
    };
    const t0 = performance.now();
    try {
      const res = await apiFetch<PredictHnResponse>("/api/predict-hn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setLastResponseMs(Math.round(performance.now() - t0));
      setLastQuery({ method: "POST", path: "/api/predict-hn", body });
      setData(res);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [title, domain, hourUtc, dateStr, pinTime, titleLength, pinLength, similarLimit, defaults]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      onSubmit();
    }
  };

  const dispDomain = domain.trim() || (data ? domainFromTitle(data.input.title) : "");
  const clock = pinTime
    ? fmtClock(dateStr, hourUtc)
    : fmtClock(defaults.date, defaults.hour_utc);
  const effectiveDow = pinTime ? dowFromIso(dateStr) : defaults.day_of_week;

  return (
    <div className="app">
      <Nav routes={ROUTES} />
      <main className="main">
        <HnTopBar subtitle="predict | the data-backed kind" />
        <div className="content hn-content">
          {/* Submit form — modeled after HN's submit page */}
          <section id="predict" className="hn-form-card">
            <table className="hn-form-table" cellPadding={4}>
              <tbody>
                <tr>
                  <td className="hn-form-label">title</td>
                  <td>
                    <textarea
                      ref={titleRef}
                      className="hn-title-input"
                      placeholder="paste a draft HN title…"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      onKeyDown={handleKey}
                      rows={1}
                      maxLength={500}
                    />
                  </td>
                </tr>
                <tr>
                  <td className="hn-form-label">domain</td>
                  <td>
                    <input
                      className="hn-text-input"
                      type="text"
                      placeholder="(optional) e.g. github.com"
                      value={domain}
                      onChange={(e) => setDomain(e.target.value)}
                    />
                  </td>
                </tr>
                <tr>
                  <td className="hn-form-label">posting</td>
                  <td>
                    <input
                      className="hn-text-input"
                      type="date"
                      value={dateStr}
                      disabled={!pinTime}
                      onChange={(e) => setDateStr(e.target.value || defaults.date)}
                      title="UTC date — Aito only knows day-of-week, the date is a convenience"
                    />
                    {" "}
                    <span className="hn-meta-line">({DAYS[effectiveDow]})</span>
                    {" "}
                    <select
                      className="hn-text-input"
                      value={hourUtc}
                      disabled={!pinTime}
                      onChange={(e) => setHourUtc(parseInt(e.target.value, 10))}
                    >
                      {Array.from({ length: 24 }, (_, h) => (
                        <option key={h} value={h}>{h.toString().padStart(2, "0")}:00 UTC</option>
                      ))}
                    </select>
                    {" "}
                    <button
                      type="button"
                      className="hn-link-btn"
                      onClick={() => setPinTime((p) => !p)}
                    >
                      [{pinTime ? "custom" : "now"}]
                    </button>
                  </td>
                </tr>
                <tr>
                  <td className="hn-form-label">length</td>
                  <td>
                    <input
                      className="hn-text-input hn-num-input"
                      type="number"
                      min={1}
                      max={500}
                      value={pinLength ? titleLength : derivedLength}
                      disabled={!pinLength}
                      onChange={(e) =>
                        setTitleLength(Math.max(1, Math.min(500, parseInt(e.target.value || "1", 10))))
                      }
                    />
                    {" "}
                    <span className="hn-meta-line">chars</span>
                    {" "}
                    <button
                      type="button"
                      className="hn-link-btn"
                      onClick={() => {
                        if (!pinLength) setTitleLength(derivedLength || 1);
                        setPinLength((p) => !p);
                      }}
                    >
                      [{pinLength ? "custom" : "auto"}]
                    </button>
                    {pinLength && titleLength !== derivedLength && (
                      <span className="hn-meta-line">
                        {" "}— actual title is {derivedLength} chars
                      </span>
                    )}
                  </td>
                </tr>
                <tr>
                  <td className="hn-form-label">similar</td>
                  <td>
                    <input
                      className="hn-text-input hn-num-input"
                      type="number"
                      min={3}
                      max={30}
                      value={similarLimit}
                      onChange={(e) =>
                        setSimilarLimit(Math.max(3, Math.min(30, parseInt(e.target.value || "8", 10))))
                      }
                    />
                    {" "}
                    <span className="hn-meta-line">past submissions to surface (3–30)</span>
                  </td>
                </tr>
                <tr>
                  <td />
                  <td>
                    <button
                      className="hn-submit-btn"
                      onClick={onSubmit}
                      disabled={loading || !title.trim()}
                    >
                      {loading ? "predicting…" : "predict"}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            {!data && !error && (
              <div id="examples" className="hn-examples">
                <div className="hn-section-label">first time? try one:</div>
                <ol className="hn-examples-list">
                  {EXAMPLE_TITLES.map((ex, i) => (
                    <li key={i}>
                      <button className="hn-link-btn" onClick={() => setTitle(ex.title)}>
                        {ex.title}
                      </button>
                      <span className="hn-meta-line"> ({ex.hint})</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </section>

          {error && <ErrorState error={error} />}

          {data && (
            <>
              {/* Predicted post — rendered like an HN story entry,
                  with prediction badges as the meta line. */}
              <section className="hn-result-card">
                <ol className="hn-storylist hn-storylist-result">
                  <li className="hn-story hn-story-prediction">
                    <span className="hn-story-rank">1.</span>
                    <span className="hn-story-vote">▲</span>
                    <div className="hn-story-body">
                      <div className="hn-story-titleline">
                        <span className="hn-story-title">{data.input.title}</span>
                        {dispDomain && (
                          <span className="hn-story-domain"> ({dispDomain})</span>
                        )}
                      </div>
                      <div className="hn-story-meta">
                        <span className="hn-pred-pill">
                          {data.headline.band} odds
                        </span>
                        {" "}|{" "}
                        <strong>{data.headline.front_page_pct.toFixed(1)}%</strong>
                        {" "}front page vs{" "}
                        {data.headline.base_rate_pct.toFixed(1)}% for a typical
                        {" "}submission ({data.headline.relative_to_base.toFixed(2)}x)
                        {" "}|{" "}
                        ~{Math.round(data.estimated_score.most_likely_midpoint)} points
                        {" "}|{" "}
                        ~{Math.round(data.estimated_comments)} comments
                        {" "}|{" "}
                        {clock}
                      </div>
                      <div className="hn-story-meta hn-meta-line">
                        Aito&rsquo;s raw output was{" "}
                        {data.headline.raw_front_page_pct.toFixed(1)}%; shown
                        {" "}calibrated against a held-out sample, where raw
                        {" "}predictions above 20% came true about half as often
                        {" "}as claimed. <a href="#accuracy">How accurate is this?</a>
                      </div>
                    </div>
                  </li>
                </ol>
              </section>

              {/* The evidence, first. These are real past submissions
                  sharing the input's words, and their spread is the
                  honest answer to "what will happen to my post" — a
                  wide one. The prediction above is a summary of this,
                  not a separate source of truth. */}
              <section id="similar" className="hn-block">
                <div className="hn-block-title">
                  similar past submissions
                  <span className="hn-meta-line"> — same words, wildly different outcomes</span>
                </div>
                <div className="hn-similar-row">
                  <div className="hn-similar-list-col">
                    <SimilarPosts posts={data.similar_posts} />
                  </div>
                  <div className="hn-similar-dist-col">
                    <SimilarDistribution posts={data.similar_posts} />
                  </div>
                </div>
              </section>

              {/* Outcome distribution as a compact widget */}
              <section className="hn-block">
                <div className="hn-block-title">
                  outcome distribution
                  <span className="hn-meta-line"> — what Aito infers from the corpus</span>
                </div>
                <BucketBar distribution={data.bucket_distribution} />
              </section>

              <section id="accuracy" className="hn-block hn-accuracy">
                <div className="hn-block-title">how accurate is this?</div>
                <p>
                  Not very, and we measured it rather than guessing.
                  Scoring 900 submissions posted <em>after</em> the corpus
                  ends — so the index has never seen them — the front-page
                  prediction gets <strong>AUC 0.599</strong>, where 0.5 is a
                  coin flip. The top-decile predictions reach the front page{" "}
                  <strong>1.9x</strong> as often as a typical submission, so it
                  is not nothing. It is also not a crystal ball.
                </p>
                <p>
                  The uncomfortable part: <strong>the title barely matters.</strong>{" "}
                  Predicting from the title alone scores AUC 0.514 — noise.
                  Predicting from the <em>domain</em>{" "}alone scores 0.607, which
                  beats the full model. Whatever signal exists here is mostly
                  &ldquo;which site are you linking to,&rdquo; not how you worded it.
                </p>
                <p className="hn-meta-line">
                  Reproduce it yourself:{" "}
                  <code>uv run python -m scripts.evaluate</code> in{" "}
                  <a
                    href="https://github.com/AitoDotAI/aito-hacker-news-demo"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    the repo
                  </a>
                  . The corpus is 200,000 submissions from 2023-05-25 to
                  2024-01-12, so the &ldquo;similar past submissions&rdquo; above
                  are drawn from that window.
                </p>
              </section>

              <div className="hn-footnote">
                <a href="#predict">predict another</a> {" | "}
                {lastResponseMs ?? "—"} ms via {" "}
                <a href="https://aito.ai" target="_blank" rel="noopener noreferrer">
                  aito, an inference database
                </a>
                {" | "}
                <a
                  href="https://aito.ai/?utm_source=hn-predictor&utm_medium=demo&utm_campaign=show_hn"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  what is Aito?
                </a>
              </div>
            </>
          )}
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
