/**
 * Amplitude + GA4 analytics for the Predictive Ledger demo.
 *
 * SURFACE identifies which Aito surface emitted the event so the
 * shared Amplitude workspace can slice cross-surface funnels
 * (landing → demo → console).
 *
 * API key and GA4 measurement ID are provisioned at build time via
 * aito-demo-server's `env_secrets` (sourced from Azure Key Vault);
 * they reach this bundle as `NEXT_PUBLIC_*` env vars baked in by
 * `next build`. Never read or commit literals here.
 */

import * as amplitude from "@amplitude/analytics-browser";

const SURFACE = "accounting-demo";

type Props = Record<string, unknown>;
type Traits = Record<string, unknown>;

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

let initialized = false;

function isProductionHost(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host !== "localhost" && host !== "127.0.0.1" && !host.endsWith(".local");
}

function isBotUserAgent(): boolean {
  if (typeof navigator === "undefined") return false;
  return /bot|crawler|spider|crawling|preview|headless/i.test(navigator.userAgent);
}

function gtagSafe(...args: unknown[]): void {
  if (typeof window !== "undefined" && window.gtag) {
    window.gtag(...args);
  }
}

/** Initialize Amplitude. Idempotent — safe to call from multiple
 *  components or React strict-mode double effects. */
export function initAnalytics(): void {
  if (initialized) return;
  if (typeof window === "undefined") return;
  if (!isProductionHost()) return;
  if (isBotUserAgent()) return;

  const amplitudeKey = process.env.NEXT_PUBLIC_AMPLITUDE_KEY;
  if (!amplitudeKey) {
    console.warn("[analytics] NEXT_PUBLIC_AMPLITUDE_KEY not set; Amplitude disabled.");
    initialized = true;
    return;
  }

  amplitude.init(amplitudeKey, {
    serverZone: "EU",
    cookieOptions: { domain: ".aito.ai" },
    defaultTracking: {
      // Disabled — `trackPage()` is the source of truth for page views
      // (App Router soft navigations don't fire history events reliably,
      // and defaultTracking would produce a second event under a
      // different name `[Amplitude] Page Viewed`).
      pageViews: false,
      sessions: true,
      formInteractions: false,
      fileDownloads: false,
    },
  });

  initialized = true;
}

export function trackPage(pageName: string, properties: Props = {}): void {
  if (typeof window === "undefined") return;
  const withSurface = { ...properties, surface: SURFACE };
  amplitude.track(`Page View: ${pageName}`, withSurface);
  gtagSafe("event", "page_view", { page_title: pageName, ...withSurface });
}

export function trackEvent(event: string, properties: Props = {}): void {
  if (typeof window === "undefined") return;
  const withSurface = { ...properties, surface: SURFACE };
  amplitude.track(event, withSurface);
  gtagSafe("event", event, withSurface);
}

export function identifyUser(userId: string, traits: Traits = {}): void {
  if (!userId) return;
  if (typeof window === "undefined") return;
  amplitude.setUserId(userId);
  const id = new amplitude.Identify();
  Object.entries(traits).forEach(([k, v]) => id.set(k, v as never));
  amplitude.identify(id);
  gtagSafe("set", { user_id: userId, ...traits });
}
