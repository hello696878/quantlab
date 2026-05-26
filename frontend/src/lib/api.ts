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

export async function runBacktest(
  params: BacktestRequest,
): Promise<BacktestResponse> {
  const res = await fetch("/api/backtest/sma-crossover", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") message = body.detail;
      else if (Array.isArray(body?.detail))
        message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
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
