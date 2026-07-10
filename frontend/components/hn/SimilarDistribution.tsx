"use client";

import type { SimilarPost, SuccessBucket } from "@/lib/hn-types";

/**
 * Compact flop..viral distribution computed from the displayed
 * similar past submissions — so the user can see at a glance whether
 * the closest analogs all flopped, all went viral, or split.
 *
 * Reuses the per-bucket-row format from BucketBar but stripped down
 * (no $why factors, smaller). Shows counts + percentages.
 */

const BUCKETS: SuccessBucket[] = ["flop", "low", "mid", "hit", "viral"];

const COLORS: Record<SuccessBucket, string> = {
  flop: "#828282",
  low: "#5a7a8a",
  mid: "#3a8a6b",
  hit: "#d49830",
  viral: "#ff6600",
};

interface Props {
  posts: SimilarPost[];
}

export default function SimilarDistribution({ posts }: Props) {
  const total = posts.length;
  if (total === 0) {
    return (
      <div className="hn-simdist-empty">no similar posts to distribute</div>
    );
  }
  const counts: Record<SuccessBucket, number> = {
    flop: 0, low: 0, mid: 0, hit: 0, viral: 0,
  };
  for (const p of posts) counts[p.success_bucket] = (counts[p.success_bucket] ?? 0) + 1;

  const maxCount = Math.max(...Object.values(counts), 1);

  return (
    <div className="hn-simdist">
      <div className="hn-simdist-head">
        outcome of {total} similar past submission{total === 1 ? "" : "s"}:
      </div>
      <ol className="hn-simdist-rows">
        {BUCKETS.map((b) => {
          const n = counts[b];
          const pct = (n / total) * 100;
          const width = (n / maxCount) * 100;
          return (
            <li key={b} className="hn-simdist-row">
              <span className="hn-simdist-label">{b}</span>
              <span className="hn-simdist-bar-cell">
                <span
                  className="hn-simdist-bar-fill"
                  style={{ width: `${width}%`, background: COLORS[b] }}
                />
              </span>
              <span className="hn-simdist-count">
                {n}
                <span className="hn-simdist-pct"> ({pct.toFixed(0)}%)</span>
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
