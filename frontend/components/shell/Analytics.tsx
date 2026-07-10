"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { initAnalytics, trackPage } from "@/lib/analytics";

/**
 * Initialize Amplitude on first mount and emit a page-view event on
 * every client-side route change. The Next.js App Router doesn't
 * fire a real navigation for SPA route changes, so without this
 * only the initial landing page would show up in Amplitude.
 */
export default function Analytics() {
  const pathname = usePathname();

  useEffect(() => {
    initAnalytics();
  }, []);

  useEffect(() => {
    if (!pathname) return;
    trackPage(pathname);
  }, [pathname]);

  return null;
}
