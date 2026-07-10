"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export interface NavRoute {
  href: string;
  label: string;
  /** Optional emoji/character shown before the label. */
  icon?: string;
}

interface NavProps {
  /** Routes shown in the sidebar — usually one per top-level page. */
  routes: NavRoute[];
}

/**
 * Generic left-sidebar nav. Pass the routes you want shown; the active
 * route is auto-detected from the current pathname.
 *
 * For a single-page demo you can skip this entirely — just render
 * `<TopBar>` and the page content.
 *
 * The accounting reference Nav also includes customer-scoped counts
 * (invoice totals, etc.) via `useCustomer()`. Lift from
 * `aito-accounting-demo/frontend/components/shell/Nav.tsx` and adapt
 * when you need that.
 */
export default function Nav({ routes }: NavProps) {
  const pathname = usePathname();

  if (routes.length === 0) return null;

  return (
    <nav className="nav">
      {routes.map((r) => {
        const active = pathname === r.href || (r.href !== "/" && pathname?.startsWith(r.href));
        return (
          <Link
            key={r.href}
            href={r.href}
            className={`nav-item${active ? " nav-item-active" : ""}`}
          >
            {r.icon && <span className="nav-icon" aria-hidden>{r.icon}</span>}
            <span>{r.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
