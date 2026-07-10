const API_BASE = typeof window !== "undefined"
  ? `${window.location.protocol}//${window.location.host}`
  : "";

export class ApiError extends Error {
  status: number;
  detail: string | null;
  constructor(status: number, detail: string | null, path: string) {
    super(detail || `API ${status}: ${path}`);
    this.status = status;
    this.detail = detail;
  }
}

export interface AitoLatencySample {
  ms: number;
  calls: number;
  path: string;
  at: number;
  /** Per-Aito-call breakdown: e.g. [{op:"_predict", ms:28.4}, {op:"_relate", ms:142.0}].
   *  Sourced from the X-Aito-Ops response header. Empty when the request
   *  didn't hit Aito or the backend is older than the per-op breakdown. */
  ops: { op: string; ms: number }[];
}

type LatencyListener = (sample: AitoLatencySample) => void;
const latencyListeners = new Set<LatencyListener>();

export function onAitoLatency(fn: LatencyListener): () => void {
  latencyListeners.add(fn);
  return () => {
    // Set.delete() returns boolean; a void cleanup callback is what
    // React effects expect, so wrap explicitly rather than rely on
    // type coercion.
    latencyListeners.delete(fn);
  };
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  // Surface Aito round-trip ms whenever the backend signals it via
  // X-Aito-Ms (set per-request when any AitoClient call ran). Listeners
  // power the topbar latency badge; endpoints that didn't hit Aito
  // simply emit nothing.
  const ms = res.headers.get("X-Aito-Ms");
  const calls = res.headers.get("X-Aito-Calls");
  const opsHeader = res.headers.get("X-Aito-Ops");
  if (ms != null) {
    const ops = opsHeader
      ? opsHeader.split(",").map((entry) => {
          const i = entry.lastIndexOf(":");
          return i < 0
            ? { op: entry, ms: NaN }
            : { op: entry.slice(0, i), ms: parseFloat(entry.slice(i + 1)) };
        })
      : [];
    const sample: AitoLatencySample = {
      ms: parseFloat(ms),
      calls: parseInt(calls || "1", 10) || 1,
      path,
      at: Date.now(),
      ops,
    };
    for (const fn of latencyListeners) {
      try { fn(sample); } catch { /* listener error must not break API call */ }
    }
  }
  if (!res.ok) {
    let detail: string | null = null;
    try {
      const body = await res.clone().json();
      detail = body?.error || body?.detail || null;
    } catch {}
    throw new ApiError(res.status, detail, path);
  }
  return res.json();
}

export function fmtAmount(n: number): string {
  return "\u20AC" + n.toLocaleString("fi-FI", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function confClass(p: number): string {
  if (p >= 0.80) return "conf-high";
  if (p >= 0.50) return "conf-mid";
  return "conf-low";
}
