// Types for /api/predict-hn (matches src/predict_service.py models).

export type SuccessBucket = "flop" | "low" | "mid" | "hit" | "viral";

export interface PredictHnInput {
  title: string;
  domain?: string | null;
  hour_utc?: number | null;
  day_of_week?: number | null;
  title_length?: number | null;
  similar_limit?: number | null;
}

export interface BucketProbability {
  bucket: SuccessBucket;
  label: string;
  probability: number;
  why_factors: WhyFactor[];
}

export interface SimilarPost {
  title: string;
  url: string | null;
  domain: string;
  score: number;
  comments: number;
  success_bucket: SuccessBucket;
  created_at: string | null;
  similarity: number | null;
}

export interface WhyFactor {
  field: string;
  value: unknown;
  weight: number | null;
}

export interface EstimatedScore {
  expected: number;
  most_likely_bucket: SuccessBucket;
  most_likely_midpoint: number;
}

export interface PredictHnResponse {
  input: PredictHnInput;
  derived: {
    is_show_hn: boolean;
    is_ask_hn: boolean;
    title_length: number;
  };
  headline: {
    front_page_pct: number;
    label: string;
  };
  bucket_distribution: BucketProbability[];
  estimated_score: EstimatedScore;
  estimated_comments: number;
  similar_posts: SimilarPost[];
  aito_calls: Array<{ op: string; [k: string]: unknown }>;
}

// Example titles shown on first load. One known-flop, one known-mid,
// one known-viral pattern.
export const EXAMPLE_TITLES: { label: string; title: string; hint: string }[] = [
  {
    label: "Show HN classic",
    title: "Show HN: A minimal Postgres client written in Rust",
    hint: "Show HN format, technical, generic — usually mid-bucket",
  },
  {
    label: "Hot topic",
    title: "OpenAI announces new model with breakthrough reasoning",
    hint: "Big-name + hype keywords — historically viral",
  },
  {
    label: "Long shot",
    title: "I built a todo app over the weekend",
    hint: "Generic, no specifics — typically flops",
  },
];

// 0=Mon..6=Sun. Display labels used in the UI selector.
export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

// ── Category features (GET /api/category-features) ──────────────────

export interface FeatureHit {
  value: string | number;
  lift: number;
  count_in_bucket: number;
  count_total: number;
  p_in_bucket: number;
  p_overall: number;
}

export interface FieldFeatures {
  field: string;
  label: string;
  hits: FeatureHit[];
}

export interface BucketFeatures {
  bucket: SuccessBucket;
  label: string;
  row_count: number;
  fields: FieldFeatures[];
}

export interface CategoryFeaturesResponse {
  table: string;
  total_rows: number;
  buckets: BucketFeatures[];
  aito_calls: number;
}
