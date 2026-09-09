"use client";

import type { SimilarPost, SuccessBucket } from "@/lib/hn-types";

/**
 * "Same words, wildly different outcomes" — the educational payoff of the
 * demo. Show 5–8 nearest past submissions by title similarity, with their
 * actual upvote/comment counts. Same-words-different-outcome is what
 * makes HN feel random; we're saying "Aito knows the population spread,
 * not just the mean."
 */

const BUCKET_COLOR: Record<SuccessBucket, string> = {
  flop: "#5a5a5a",
  low: "#7a8aa0",
  mid: "#3a8a6b",
  hit: "#d49830",
  viral: "#ff6600",
};

function hnUrl(post: SimilarPost): string {
  // If URL is missing or self-post, link to the HN search for the title
  // (we don't have story IDs in the response).
  if (post.url) return post.url;
  return `https://hn.algolia.com/?query=${encodeURIComponent(post.title)}&type=story`;
}

function fmtAgo(iso: string | null): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const days = Math.floor((Date.now() - t) / (1000 * 60 * 60 * 24));
  if (days < 1) return "today";
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
}

interface Props {
  posts: SimilarPost[];
}

export default function SimilarPosts({ posts }: Props) {
  if (!posts.length) {
    return (
      <div className="similar-empty">No similar past submissions found.</div>
    );
  }
  return (
    <ul className="similar-list">
      {posts.map((p, i) => (
        <li key={i} className="similar-item">
          <a className="similar-title" href={hnUrl(p)} target="_blank" rel="noopener noreferrer">
            {p.title}
          </a>
          <div className="similar-meta">
            <span
              className="similar-bucket"
              style={{ background: BUCKET_COLOR[p.success_bucket] + "22", color: BUCKET_COLOR[p.success_bucket] }}
            >
              {p.success_bucket}
            </span>
            <span className="similar-score">
              {p.score.toLocaleString()} {p.score === 1 ? "point" : "points"}
            </span>
            <span className="similar-comments">
              {p.comments} {p.comments === 1 ? "comment" : "comments"}
            </span>
            <span className="similar-domain">{p.domain}</span>
            {p.created_at && <span className="similar-ago">{fmtAgo(p.created_at)}</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}
