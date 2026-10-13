/**
 * The evaluation summary the page quotes, written by
 * scripts/publish_eval.py. Import numbers from here, never type them.
 */
import raw from "@/lib/eval-summary.json";

type Delta = { delta: number; lo: number; hi: number; n: number };
type AblationRow = { auc: number; lift: number; n: number; vs_shipped?: Delta | null };

// Shape written by scripts/publish_eval.py. Declared rather than inferred:
// an empty `comparisons` array in the JSON would otherwise type as never[].
export interface EvalSummary {
  corpus: { rows: number; oldest: string; newest: string };
  holdout: { n: number; start: string; end: string; base_rate: number };
  shipped: {
    auc: number;
    auc_ci95?: [number, number] | null;
    lift: number;
    top_decile_rate: number;
    bottom_decile_rate: number;
    /** Share of held-out predictions Aito clamped to its probability floor. */
    floored_share?: number | null;
  };
  calibration: { predicted: number; observed: number; n: number }[];
  calibration_min_n: number;
  calibration_out_of_sample: boolean;
  ablation: Record<"title" | "domain" | "title_domain" | "hour" | "length", AblationRow> &
    Partial<Record<"shipped_domain" | "shipped_no_time" | "title_domain_flags", AblationRow>>;
  comparisons: { label: string; corpus_newest: string; auc: number; same_holdout: boolean }[];
  why_invariant: { checked: number; failures: number };
}

export const EVAL = raw as unknown as EvalSummary;
