/**
 * API client for the QuantLab FastAPI backend.
 *
 * All requests go to /api/* which Next.js rewrites to the backend URL
 * (see next.config.js).  This avoids any browser-level CORS concerns.
 */

import type {
  BacktestRequest,
  BacktestResponse,
  BbBacktestRequest,
  CustomStrategyRequest,
  CustomStrategyTemplateCreate,
  CustomStrategyTemplateExport,
  CustomStrategyTemplateFull,
  CustomStrategyTemplateSummary,
  DeleteResponse,
  MomentumBacktestRequest,
  PairsBacktestRequest,
  RsiBacktestRequest,
  SavedBacktestCreate,
  SavedBacktestFull,
  SavedBacktestSummary,
  SmaSweepRequest,
  SmaSweepResponse,
  SmaTrainTestRequest,
  SmaTrainTestResponse,
  SmaWalkForwardRequest,
  SmaWalkForwardResponse,
  StrategyComparisonRequest,
  StrategyComparisonResponse,
  VbBacktestRequest,
} from "./types";

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

async function postBacktest(
  endpoint: string,
  params:
    | BacktestRequest
    | RsiBacktestRequest
    | BbBacktestRequest
    | MomentumBacktestRequest
    | VbBacktestRequest
    | PairsBacktestRequest,
): Promise<BacktestResponse> {
  let res: Response;
  try {
    res = await fetch(endpoint, {
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

/** POST /api/backtest/sma-crossover */
export async function runBacktest(
  params: BacktestRequest,
): Promise<BacktestResponse> {
  return postBacktest("/api/backtest/sma-crossover", params);
}

/** POST /api/backtest/rsi-mean-reversion */
export async function runRsiBacktest(
  params: RsiBacktestRequest,
): Promise<BacktestResponse> {
  return postBacktest("/api/backtest/rsi-mean-reversion", params);
}

/** POST /api/backtest/bollinger-band */
export async function runBbBacktest(
  params: BbBacktestRequest,
): Promise<BacktestResponse> {
  return postBacktest("/api/backtest/bollinger-band", params);
}

/** POST /api/backtest/momentum */
export async function runMomentumBacktest(
  params: MomentumBacktestRequest,
): Promise<BacktestResponse> {
  return postBacktest("/api/backtest/momentum", params);
}

/** POST /api/backtest/volatility-breakout */
export async function runVbBacktest(
  params: VbBacktestRequest,
): Promise<BacktestResponse> {
  return postBacktest("/api/backtest/volatility-breakout", params);
}

/** POST /api/backtest/pairs */
export async function runPairsBacktest(
  params: PairsBacktestRequest,
): Promise<BacktestResponse> {
  return postBacktest("/api/backtest/pairs", params);
}

/** POST /api/backtest/custom — no-code custom rule strategy */
export async function runCustomBacktest(
  params: CustomStrategyRequest,
): Promise<BacktestResponse> {
  let res: Response;
  try {
    res = await fetch("/api/backtest/custom", {
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

/** POST /api/research/sma-parameter-sweep */
export async function runSmaSweep(
  params: SmaSweepRequest,
): Promise<SmaSweepResponse> {
  let res: Response;
  try {
    res = await fetch("/api/research/sma-parameter-sweep", {
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

  return res.json() as Promise<SmaSweepResponse>;
}

/** POST /api/research/sma-train-test */
export async function runSmaTrainTest(
  params: SmaTrainTestRequest,
): Promise<SmaTrainTestResponse> {
  let res: Response;
  try {
    res = await fetch("/api/research/sma-train-test", {
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

  return res.json() as Promise<SmaTrainTestResponse>;
}

/** POST /api/research/sma-walk-forward */
export async function runSmaWalkForward(
  params: SmaWalkForwardRequest,
): Promise<SmaWalkForwardResponse> {
  let res: Response;
  try {
    res = await fetch("/api/research/sma-walk-forward", {
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

  return res.json() as Promise<SmaWalkForwardResponse>;
}

/** POST /api/research/strategy-comparison */
export async function runStrategyComparison(
  params: StrategyComparisonRequest,
): Promise<StrategyComparisonResponse> {
  let res: Response;
  try {
    res = await fetch("/api/research/strategy-comparison", {
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

  return res.json() as Promise<StrategyComparisonResponse>;
}

/**
 * POST /api/backtest/csv  (multipart upload)
 *
 * Uploads a price CSV plus a strategy id and a JSON params object, and runs a
 * single-asset backtest on the uploaded data.  Do NOT set Content-Type — the
 * browser sets the multipart boundary automatically for FormData.
 */
export async function runCsvBacktest(
  file: File,
  strategy: string,
  params: Record<string, unknown>,
): Promise<BacktestResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("strategy", strategy);
  form.append("params", JSON.stringify(params));

  let res: Response;
  try {
    res = await fetch("/api/backtest/csv", { method: "POST", body: form });
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

// ---------------------------------------------------------------------------
// Saved Backtests
// ---------------------------------------------------------------------------

async function savedBacktestsRequest<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(endpoint, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new BacktestApiError(0, backendUnavailableMessage(0));
  }

  if (!res.ok) {
    let message =
      res.status >= 500
        ? backendUnavailableMessage(res.status)
        : `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = formatBackendDetail(body?.detail) ?? message;
    } catch {
      // keep the HTTP status message
    }
    throw new BacktestApiError(res.status, message);
  }

  return res.json() as Promise<T>;
}

/** POST /api/saved-backtests */
export async function createSavedBacktest(
  data: SavedBacktestCreate,
): Promise<SavedBacktestFull> {
  return savedBacktestsRequest<SavedBacktestFull>("/api/saved-backtests", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** GET /api/saved-backtests */
export async function listSavedBacktests(): Promise<SavedBacktestSummary[]> {
  return savedBacktestsRequest<SavedBacktestSummary[]>("/api/saved-backtests", {
    method: "GET",
  });
}

/** GET /api/saved-backtests/{id} */
export async function getSavedBacktest(id: number): Promise<SavedBacktestFull> {
  return savedBacktestsRequest<SavedBacktestFull>(
    `/api/saved-backtests/${id}`,
    { method: "GET" },
  );
}

/** DELETE /api/saved-backtests/{id} */
export async function deleteSavedBacktest(id: number): Promise<DeleteResponse> {
  return savedBacktestsRequest<DeleteResponse>(
    `/api/saved-backtests/${id}`,
    { method: "DELETE" },
  );
}

// ---------------------------------------------------------------------------
// Saved Custom Strategy Templates
// ---------------------------------------------------------------------------

/** POST /api/custom-strategies */
export async function createCustomStrategyTemplate(
  data: CustomStrategyTemplateCreate,
): Promise<CustomStrategyTemplateFull> {
  return savedBacktestsRequest<CustomStrategyTemplateFull>("/api/custom-strategies", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/** GET /api/custom-strategies */
export async function listCustomStrategyTemplates(): Promise<
  CustomStrategyTemplateSummary[]
> {
  return savedBacktestsRequest<CustomStrategyTemplateSummary[]>(
    "/api/custom-strategies",
    { method: "GET" },
  );
}

/** GET /api/custom-strategies/{id} */
export async function getCustomStrategyTemplate(
  id: number,
): Promise<CustomStrategyTemplateFull> {
  return savedBacktestsRequest<CustomStrategyTemplateFull>(
    `/api/custom-strategies/${id}`,
    { method: "GET" },
  );
}

/** PUT /api/custom-strategies/{id} */
export async function updateCustomStrategyTemplate(
  id: number,
  data: CustomStrategyTemplateCreate,
): Promise<CustomStrategyTemplateFull> {
  return savedBacktestsRequest<CustomStrategyTemplateFull>(
    `/api/custom-strategies/${id}`,
    { method: "PUT", body: JSON.stringify(data) },
  );
}

/** DELETE /api/custom-strategies/{id} */
export async function deleteCustomStrategyTemplate(
  id: number,
): Promise<DeleteResponse> {
  return savedBacktestsRequest<DeleteResponse>(
    `/api/custom-strategies/${id}`,
    { method: "DELETE" },
  );
}

/** GET /api/custom-strategies/{id}/export — portable JSON (no id/timestamps) */
export async function exportCustomStrategyTemplate(
  id: number,
): Promise<CustomStrategyTemplateExport> {
  return savedBacktestsRequest<CustomStrategyTemplateExport>(
    `/api/custom-strategies/${id}/export`,
    { method: "GET" },
  );
}

/**
 * POST /api/custom-strategies/import — validate a portable JSON document and
 * persist it as a new template.  The backend performs all validation; `doc`
 * is the parsed contents of an uploaded file.
 */
export async function importCustomStrategyTemplate(
  doc: unknown,
): Promise<CustomStrategyTemplateFull> {
  return savedBacktestsRequest<CustomStrategyTemplateFull>(
    "/api/custom-strategies/import",
    { method: "POST", body: JSON.stringify(doc) },
  );
}
