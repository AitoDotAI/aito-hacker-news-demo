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
    /** Calibrated against a held-out sample — see src/calibration.py. */
    front_page_pct: number;
    /** Aito's uncorrected output, shown alongside so we're not hiding it. */
    raw_front_page_pct: number;
    /** Front-page rate of a typical submission, for comparison. */
    base_rate_pct: number;
    /** front_page_pct / base_rate_pct. 1.0 = indistinguishable from average. */
    relative_to_base: number;
    band: string;
    label: string;
  };
  bucket_distribution: BucketProbability[];
  estimated_score: EstimatedScore;
  estimated_comments: number;
  similar_posts: SimilarPost[];
  aito_calls: Array<{ op: string; [k: string]: unknown }>;
}

// Example titles shown on first load. The hints describe the *shape* of
// each title, not a promised outcome — the holdout evaluation found title
// wording carries almost no signal (AUC 0.514), so claiming "historically
// viral" for a phrasing would be asserting something we measured to be
// false. Try them and compare; that disagreement is the point of the demo.
export const EXAMPLE_TITLES: { label: string; title: string; hint: string }[] = [
  {
    label: "Show HN classic",
    title: "Show HN: A minimal Postgres client written in Rust",
    hint: "the canonical Show HN shape",
  },
  {
    label: "Hot topic",
    title: "OpenAI announces new model with breakthrough reasoning",
    hint: "big name, hype words",
  },
  {
    label: "Vague",
    title: "I built a todo app over the weekend",
    hint: "no specifics, no hook",
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
