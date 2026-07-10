"use client";

import Link from "next/link";
import LatencyBadge from "./LatencyBadge";

interface TopBarProps {
  /** Demo name shown next to the Aito wordmark. */
  brand: string;
  /** Optional: small breadcrumb above the page title. */
  breadcrumb?: string;
  /** Page title shown in the topbar's left side. */
  title: string;
  /** Optional subtitle next to the title. */
  subtitle?: string;
  /** Custom action buttons / selectors on the right. */
  actions?: React.ReactNode;
  /** Show a "Live" dot indicating real Aito traffic. */
  live?: boolean;
  /** Override the GitHub link (default: empty — hide the button). */
  githubUrl?: string;
}

/**
 * Generic TopBar for an Aito demo. The accounting reference TopBar adds
 * a CustomerSelector + StartTourButton + ColdStartBanner; add those back
 * in your demo if you need them (they live in aito-accounting-demo's
 * components/shell/ — lift verbatim, generalize as needed).
 *
 * Always include `<LatencyBadge />` somewhere on the page so users see
 * how fast Aito actually is.
 */
export default function TopBar({
  brand,
  breadcrumb,
  title,
  subtitle,
  actions,
  live,
  githubUrl,
}: TopBarProps) {
  return (
    <div className="topbar">
      <div>
        <Link href="/" className="topbar-brand">
          <span className="wordmark">aito<span className="dot">..</span></span>
          <span className="topbar-brand-sep">·</span>
          <span className="topbar-brand-demo">{brand}</span>
        </Link>
        {breadcrumb && <div className="topbar-breadcrumb">{breadcrumb}</div>}
        <div className="topbar-title">{title}</div>
      </div>
      {subtitle && (
        <>
          <div className="topbar-sep" />
          <div className="topbar-sub">{subtitle}</div>
        </>
      )}
      <div className="topbar-right">
        <LatencyBadge />
        {live && <span className="live-dot">Live</span>}
        {githubUrl && (
          <a className="topbar-link" href={githubUrl} target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
        )}
        {actions}
      </div>
    </div>
  );
}
