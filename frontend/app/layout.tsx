import type { Metadata } from "next";
import "./globals.css";
import Analytics from "@/components/shell/Analytics";
import { EVAL } from "@/lib/eval";

const TITLE = "How well can you predict the Hacker News front page?";
// Numbers come from lib/eval-summary.json (scripts/publish_eval.py), and
// the claim about stacking is conditional on them, like the on-page copy.
const N = EVAL.holdout.n.toLocaleString("en-US");
const AUC = EVAL.shipped.auc.toFixed(3);
const STACKS =
  EVAL.ablation.title_domain.auc - Math.max(EVAL.ablation.title.auc, EVAL.ablation.domain.auc) >= 0.01;
const DESCRIPTION =
  `We scored ${N} held-out submissions to find out. AUC ${AUC}: real signal, ` +
  "a long way from clairvoyance. " +
  (STACKS
    ? "Title and domain each add something the other misses. "
    : "Title and domain each carry about as much information, and combining them adds almost nothing. ") +
  `Test your own title against ${Math.round(EVAL.corpus.rows / 1000)}k past submissions.`;

// basePath-aware: the demo is served from demos.aito.ai/hacker-news, so
// absolute asset URLs need the prefix baked in at build time.
const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
const SITE = "https://demos.aito.ai" + (BASE || "/hacker-news");

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  metadataBase: new URL(SITE),
  icons: {
    icon: `${BASE}/aito-favicon.svg`,
  },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: SITE,
    siteName: "Aito",
    type: "website",
    // No BASE prefix here: Next resolves these against `metadataBase`,
    // which already carries the basePath. Prefixing again produced
    // /hacker-news/hacker-news/og.png.
    images: [{
      url: "/og.png",
      width: 1200,
      height: 630,
      alt: `Predicting the Hacker News front page: AUC ${AUC} on ${N} held-out submissions.`,
    }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: ["/og.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Analytics />
        {children}
      </body>
    </html>
  );
}
