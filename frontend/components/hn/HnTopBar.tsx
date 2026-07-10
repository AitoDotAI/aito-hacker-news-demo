"use client";

import { usePathname } from "next/navigation";
import LatencyBadge from "@/components/shell/LatencyBadge";
import { withBase } from "@/lib/api";

/**
 * HN-style topbar: orange rail with a small white-on-orange brand mark,
 * "brand | pipe-separated nav | right-side actions". Matches the visual
 * conventions of the canonical site (orange #ff6600, tiny Verdana, flat
 * borders) without reproducing the YC "Y" trademark — the mark is a
 * stylized "PH" square instead.
 */

interface Item {
  label: string;
  href: string;
  external?: boolean;
}

const LEFT_LINKS: Item[] = [
  { label: "predict", href: "/" },
  { label: "features", href: "/features" },
  { label: "api", href: "/api/schema", external: true },
];

const RIGHT_LINKS: Item[] = [
  { label: "github", href: "https://github.com/AitoDotAI", external: true },
  { label: "trial", href: "https://aito.ai/?utm_source=hn-predictor", external: true },
];

export default function HnTopBar({ subtitle }: { subtitle?: string }) {
  const pathname = usePathname() || "/";
  return (
    <div className="hn-topbar">
      <a className="hn-topbar-mark" href={withBase("/")} aria-label="Predictive HN home">
        PH
      </a>
      <a className="hn-topbar-brand" href={withBase("/")}>
        Predictive HN
      </a>
      <nav className="hn-topbar-nav">
        {LEFT_LINKS.map((item, i) => {
          const active = !item.external && pathname === item.href;
          return (
            <span key={item.label}>
              {i > 0 && <span className="hn-topbar-sep">|</span>}
              <a
                href={withBase(item.href)}
                className={active ? "hn-topbar-active" : ""}
                {...(item.external
                  ? { target: "_blank", rel: "noopener noreferrer" }
                  : {})}
              >
                {item.label}
              </a>
            </span>
          );
        })}
      </nav>
      {subtitle && <span className="hn-topbar-subtitle">{subtitle}</span>}
      <div className="hn-topbar-right">
        <LatencyBadge />
        {RIGHT_LINKS.map((item, i) => (
          <span key={item.label}>
            {i > 0 && <span className="hn-topbar-sep">|</span>}
            <a
              href={withBase(item.href)}
              {...(item.external
                ? { target: "_blank", rel: "noopener noreferrer" }
                : {})}
            >
              {item.label}
            </a>
          </span>
        ))}
      </div>
    </div>
  );
}
