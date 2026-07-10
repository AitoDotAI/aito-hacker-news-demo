import type { ApiError } from "@/lib/api";

interface ErrorStateProps {
  title?: string;
  message?: string;
  /** When provided, render a status-specific message instead of the default. */
  error?: Error | ApiError | null;
  /** When provided, renders a "Retry" button that calls this. */
  onRetry?: () => void;
}

function describe(error?: Error | ApiError | null): { title: string; message: string; showCmd: boolean } {
  // Default: backend not reachable (network error or unknown failure)
  if (!error) {
    return {
      title: "Could not load data",
      message: "Start the backend with ./do dev and reload this page.",
      showCmd: true,
    };
  }
  const status = (error as ApiError).status;
  const detail = (error as ApiError).detail;

  if (status === 400) {
    return {
      title: "Invalid request",
      message: detail || "The page sent a request the API rejected. Check the URL parameters.",
      showCmd: false,
    };
  }
  if (status === 404) {
    return {
      title: "Not found",
      message: detail || "The requested resource doesn't exist on this instance.",
      showCmd: false,
    };
  }
  if (status === 429) {
    return {
      title: "Rate limited",
      message: "Too many requests in the last minute. Wait a few seconds and reload.",
      showCmd: false,
    };
  }
  if (status >= 500) {
    return {
      title: "Backend error",
      message: detail || `Aito or the API server returned ${status}. Check the server logs.`,
      showCmd: false,
    };
  }
  return {
    title: "Could not load data",
    message: error.message || "Start the backend with ./do dev and reload this page.",
    showCmd: true,
  };
}

export default function ErrorState({ title, message, error, onRetry }: ErrorStateProps) {
  const d = describe(error);
  const finalTitle = title ?? d.title;
  const finalMessage = message ?? d.message;
  return (
    <div style={{
      padding: "48px 24px",
      textAlign: "center",
      color: "var(--text3)",
    }}>
      <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text2)", marginBottom: 8 }}>
        {finalTitle}
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.6 }}>
        {finalMessage}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn btn-outline"
          style={{ marginTop: 16, cursor: "pointer" }}
        >
          Retry
        </button>
      )}
      {d.showCmd && !onRetry && (
        <div style={{
          marginTop: 16,
          padding: "8px 14px",
          background: "var(--surface2)",
          borderRadius: 6,
          display: "inline-block",
          fontFamily: "'IBM Plex Mono', monospace",
          fontSize: 12,
        }}>
          ./do dev
        </div>
      )}
    </div>
  );
}
