/**
 * API client for the QuantLab FastAPI backend.
 *
 * All requests go to /api/* which Next.js rewrites to the backend URL
 * (see next.config.js).  This avoids any browser-level CORS concerns.
 */

import type { BacktestRequest, BacktestResponse } from "./types";

export class BacktestApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "BacktestApiError";
  }
}

function formatBackendDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return null;

  const messages = detail
    .map((d) => {
      if (!d || typeof d !== "object") return null;
      const item = d as { loc?: unknown[]; msg?: unknown };
      if (typeof item.msg !== "string") return null;
      const field =
        Array.isArray(item.loc) && item.loc.length > 0
          ? String(item.loc[item.loc.length - 1])
          : null;
      return field ? `${field}: ${item.msg}` : item.msg;
    })
    .filter((msg): msg is string => Boolean(msg));

  return messages.length > 0 ? messages.join("; ") : null;
}

function backendUnavailableMessage(status: number): string {
  return (
    `Backend request failed (HTTP ${status}). ` +
    "Make sure the FastAPI backend is running at BACKEND_URL, " +
    "or http://localhost:8000 by default."
  );
}

export async function runBacktest(
  params: BacktestRequest,
): Promise<BacktestResponse> {
  let res: Response;
  try {
    res = await fetch("/api/backtest/sma-crossover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
  } catch {
    throw new BacktestApiError(0, backendUnavailableMessage(0));
  }

  if (!res.ok) {
    let message =
      res.status >= 500 ? backendUnavailableMessage(res.status) : `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = formatBackendDetail(body?.detail) ?? message;
    } catch {
      // keep the HTTP status message
    }
    throw new BacktestApiError(res.status, message);
  }

  return res.json() as Promise<BacktestResponse>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch("/api/health");
    return res.ok;
  } catch {
    return false;
  }
}
