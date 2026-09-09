import type { Metadata } from "next";
import "./globals.css";
import Analytics from "@/components/shell/Analytics";

const TITLE = "How well can you predict the Hacker News front page?";
const DESCRIPTION =
  "We scored 2,600 held-out submissions to find out. AUC 0.623 — real signal, " +
  "a long way from clairvoyance. Title and domain each carry about as much " +
  "information, and combining them adds almost nothing. Test your own title " +
  "against 335,000 past submissions.";

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
      alt: "Predicting the Hacker News front page: AUC 0.623 on 2,600 held-out submissions.",
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
