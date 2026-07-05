/**
 * Alternative Data, News Sentiment & Signal Decay Lab — types + API client
 * (Phase 30.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/alternative-data/sample   → deterministic sample event sets
 *   POST /api/alternative-data/analyze  → sentiment / freshness / leakage / decay analytics
 *
 * All data is static illustrative sample data — no live news, social media, or
 * market data, no scraping, no LLM or provider APIs, educational only, and not
 * investment, trading, or signal advice.
 */

export type SourceType =
  | "news"
  | "social"
  | "earnings"
  | "macro"
  | "product"
  | "regulatory"
  | "supply_chain";

export interface AlternativeDataEventInput {
  event_id: string;
  timestamp: string;
  symbol: string;
  source_type: SourceType;
  headline: string;
  sentiment_score: number;
  event_intensity: number;
  novelty_score: number;
  source_reliability: number;
  relevance_score: number;
  observed_return_1d: number;
  observed_return_5d: number;
  observed_return_20d: number;
  publication_lag_minutes: number;
  feature_available_timestamp: string;
}

export interface SignalDecayPointInput {
  horizon_days: number;
  signal_value: number;
  realized_return: number;
}

export interface AlternativeDataScenarioInput {
  name: string;
  sentiment_shock: number;
  intensity_shock: number;
  novelty_shock: number;
  reliability_shock: number;
  publication_lag_shock: number;
  noise_multiplier: number;
  event_count_multiplier: number;
}

export interface AlternativeDataAnalysisRequest {
  sample_id: string;
  sample_name: string;
  events: AlternativeDataEventInput[];
  lambda_novelty: number;
  gamma_freshness_per_hour: number;
  custom_decay_points?: SignalDecayPointInput[] | null;
  custom_scenarios?: AlternativeDataScenarioInput[] | null;
}

export interface AlternativeDataSampleResponse {
  samples: AlternativeDataAnalysisRequest[];
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface SampleSummary {
  sample_id: string;
  sample_name: string;
  event_count: number;
  symbols: string[];
  source_types: string[];
}

export interface AlternativeDataEventRow {
  event_id: string;
  timestamp: string;
  symbol: string;
  source_type: SourceType;
  headline: string;
  sentiment_score: number;
  event_intensity: number;
  novelty_score: number;
  source_reliability: number;
  relevance_score: number;
  weighted_sentiment: number;
  novelty_adjusted_signal: number;
  freshness: number;
  lag_adjusted_signal: number;
  observed_return_1d: number;
  observed_return_5d: number;
  observed_return_20d: number;
  leakage_flag: boolean;
}

export interface SentimentAnalysis {
  average_sentiment: number;
  weighted_sentiment_average: number;
  positive_event_count: number;
  negative_event_count: number;
  neutral_event_count: number;
  alpha_score: number;
}

export interface FreshnessAnalysis {
  average_publication_lag_minutes: number;
  average_freshness: number;
  stale_event_count: number;
  notes: string[];
}

export interface LeakageGuard {
  leakage_count: number;
  leakage_rate: number;
  has_leakage: boolean;
  notes: string[];
}

export interface SignalQuality {
  information_coefficient_1d?: number | null;
  information_coefficient_5d?: number | null;
  information_coefficient_20d?: number | null;
  hit_rate_1d: number;
  hit_rate_5d: number;
  hit_rate_20d: number;
  signal_to_noise_score: number;
  reliability_weighted_quality: number;
  notes: string[];
}

export interface EventStudyPoint {
  horizon_days: number;
  average_forward_return: number;
  average_signal: number;
  ic_at_horizon?: number | null;
}

export interface SignalDecayPoint {
  horizon_days: number;
  decay_correlation?: number | null;
  signal_half_life_estimate?: number | null;
}

export interface RiskRegime {
  regime_id: string;
  regime_label: string;
  score: number;
  drivers: string[];
  explanation: string;
}

export interface AltDataScenarioResult {
  id: string;
  name: string;
  description: string;
  average_sentiment: number;
  average_intensity: number;
  average_novelty: number;
  average_reliability: number;
  average_freshness: number;
  alpha_score: number;
  information_coefficient_5d?: number | null;
  hit_rate_5d: number;
  leakage_count: number;
  decay_5d?: number | null;
  decay_20d?: number | null;
  regime_label: string;
  notes: string[];
}

export interface AlternativeDataAnalysisResponse {
  data_status: "static_sample";
  sample_summary: SampleSummary;
  event_table: AlternativeDataEventRow[];
  sentiment_analysis: SentimentAnalysis;
  freshness_analysis: FreshnessAnalysis;
  leakage_guard: LeakageGuard;
  signal_quality: SignalQuality;
  event_study: EventStudyPoint[];
  signal_decay: SignalDecayPoint[];
  risk_regime: RiskRegime;
  scenario_results: AltDataScenarioResult[];
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error("Backend unavailable — start the QuantLab API to use the Alternative Data Lab.");
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  } catch {
    // ignore — fall through to status text
  }
  return res.status >= 500 ? "Server error computing alternative-data analytics." : `HTTP ${res.status}`;
}

/** GET /api/alternative-data/sample */
export async function fetchAlternativeDataSample(
  signal?: AbortSignal,
): Promise<AlternativeDataSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/alternative-data/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<AlternativeDataSampleResponse>;
}

/** POST /api/alternative-data/analyze */
export async function analyzeAlternativeData(
  request: AlternativeDataAnalysisRequest,
  signal?: AbortSignal,
): Promise<AlternativeDataAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/alternative-data/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<AlternativeDataAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function num(value: number, digits = 2): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function signedNum(value: number, digits = 3): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}`;
}

export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function signedPct(value: number, digits = 2): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

/** Correlation/IC display — "—" when null (zero variance). */
export function corr(value: number | null | undefined, digits = 2): string {
  return value == null ? "—" : (value > 0 ? "+" : "") + value.toFixed(digits);
}
