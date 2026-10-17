/**
 * "How it works / how accurate is it" — always on the page, not only
 * after a prediction, because it is the first thing a sceptical reader
 * looks for.
 *
 * Every number here comes from lib/eval-summary.json, which
 * scripts/publish_eval.py writes from an evaluate.py run. Do not type
 * numbers into this file: re-run the evaluation and republish instead.
 * The sentences that interpret the numbers are conditional on them, so a
 * new run cannot leave a claim standing that the data no longer supports.
 */

import { EVAL as summary } from "@/lib/eval";

const REPO = "https://github.com/AitoDotAI/aito-hacker-news-demo";

const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
const auc = (x: number) => x.toFixed(3);
const month = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
const day = (iso: string) => iso.slice(0, 10);
const signed = (x: number) => `${x >= 0 ? "+" : "\u2212"}${Math.abs(x).toFixed(3)}`;

export function AccuracySection() {
  const s = summary;
  const a = s.ablation;
  const reliable = s.calibration.filter((b) => b.n >= s.calibration_min_n);
  const thin = s.calibration.filter((b) => b.n < s.calibration_min_n);
  const best = Math.max(a.title.auc, a.domain.auc);
  const stackGain = a.title_domain.auc - best;
  const comparisons = s.comparisons.filter((c) => c.same_holdout);
  const timeless = a.shipped_no_time?.vs_shipped;

  return (
    <section id="accuracy" className="hn-block hn-accuracy">
      <div className="hn-block-title">how it works</div>
      <p>
        Your title, domain and posting time go to{" "}
        <a href="https://aito.ai" target="_blank" rel="noopener noreferrer">Aito</a>, a
        database that answers prediction queries straight from its index. There is no
        trained model. Three queries run over {s.corpus.rows.toLocaleString("en-US")} HN
        submissions from {month(s.corpus.oldest)} to {month(s.corpus.newest)}: one for the
        score bucket, one for the front-page odds, and one for the closest past titles.
        &ldquo;Front page&rdquo; here means 50 points or more.
      </p>

      <div className="hn-block-title">how accurate is it?</div>
      <p>
        We held out {s.holdout.n.toLocaleString("en-US")} submissions posted after the
        corpus ends ({day(s.holdout.start)} to {day(s.holdout.end)}), so the index has never
        seen them, and scored them through this page&rsquo;s own code. AUC is{" "}
        <strong>{auc(s.shipped.auc)}</strong>
        {s.shipped.auc_ci95 &&
          ` (95% range ${auc(s.shipped.auc_ci95[0])} to ${auc(s.shipped.auc_ci95[1])})`}
        , where 0.5 is a coin flip and 1.0 is perfect.
        The top tenth of predictions reached the front page{" "}
        {pct(s.shipped.top_decile_rate)} of the time, against {pct(s.holdout.base_rate)} for
        all of them ({s.shipped.lift.toFixed(1)}x). Real signal, and a long way from
        knowing.
      </p>
      {reliable.length > 0 && (
        <p>
          {/* "Honest" only if every well-populated bin lands within a third
              of its prediction (or 2 points, for the small ones). */}
          {reliable.every((b) => Math.abs(b.observed - b.predicted) <= Math.max(0.02, b.predicted / 3))
            ? "The percentages mean what they say"
            : "The percentages are rough"}
          {s.calibration_out_of_sample ? ", checked on posts the calibration never saw: " : ": "}
          {reliable.map((b, i) => (
            <span key={i}>
              {i > 0 && (i === reliable.length - 1 ? " and " : ", ")}
              predictions around {pct(b.predicted)} came true {pct(b.observed)} of the time
            </span>
          ))}
          .{" "}
          {thin.length > 0 &&
            `Above ${pct(thin[0].predicted)} we have too few cases (${thin
              .map((b) => b.n)
              .reduce((x, y) => x + y, 0)}) to promise anything.`}
        </p>
      )}

      <div className="hn-block-title">what doesn&rsquo;t work</div>
      <p>
        Title alone scores {auc(a.title.auc)} and domain alone {auc(a.domain.auc)}.{" "}
        {stackGain < 0.01 ? (
          <>
            Together they score {auc(a.title_domain.auc)}, so they mostly carry the same
            information and combining them buys almost nothing.
          </>
        ) : (
          <>
            Together they score {auc(a.title_domain.auc)}, so each adds something the other
            misses.
          </>
        )}{" "}
        {timeless && timeless.n > 0 && timeless.lo <= 0 && timeless.hi >= 0 ? (
          <>
            Posting time carries nothing: hour alone scores {auc(a.hour.auc)}, and taking
            posting time out of the query moves the score by {signed(timeless.delta)} (95%
            range {signed(timeless.lo)} to {signed(timeless.hi)}).{" "}
          </>
        ) : (
          <>
            Posting hour alone scores {auc(a.hour.auc)}
            {a.hour.auc < 0.56 ? ", close to noise. " : ". "}
          </>
        )}
        Title length alone scores {auc(a.length.auc)}.{" "}
        Most of what decides a post (who submits it, the first few votes, what else is on the
        front page that hour) is not in the data at all.
      </p>
      {comparisons.length > 0 && (
        <p>
          {/* Lead chosen from the data: a corpus refresh only "matters" if
              some older corpus actually scored measurably worse. */}
          {comparisons.some((c) => s.shipped.auc - c.auc >= 0.01)
            ? "Freshness matters, up to a point. "
            : "Freshness matters less than we expected. "}
          The same {s.holdout.n.toLocaleString("en-US")} held-out posts scored against older
          copies of the corpus:{" "}
          {comparisons.map((c, i) => (
            <span key={i}>
              {i > 0 && "; "}
              one ending {month(c.corpus_newest)} gets {auc(c.auc)}
            </span>
          ))}
          , against {auc(s.shipped.auc)} for the current one, which ends{" "}
          {month(s.corpus.newest)}.
        </p>
      )}
      <p className="hn-meta-line">
        Reproduce it: <code>uv run python -m scripts.evaluate</code> in{" "}
        <a href={REPO} target="_blank" rel="noopener noreferrer">the repo</a>.
        {s.why_invariant.checked > 0 &&
          ` The run also checks that each bucket shows its own explanation (${s.why_invariant.checked} predictions, ${s.why_invariant.failures} failures).`}
      </p>
    </section>
  );
}
