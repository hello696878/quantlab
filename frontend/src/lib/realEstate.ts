/**
 * Real Estate Lab — types + API client (Phase 22.0).
 *
 * Talks to the backend static-sample analytics API:
 *   GET  /api/real-estate/sample   → deterministic sample property / debt / REIT
 *   POST /api/real-estate/analyze  → full income-property + REIT analytics
 *
 * All data is static illustrative sample data — no live property/REIT data,
 * educational only, not investment / tax / legal / lending advice.
 */

export interface PropertyInput {
  property_name: string;
  property_type: string;
  market: string;
  purchase_price: number;
  gross_rent_annual: number;
  other_income_annual: number;
  vacancy_rate: number;
  operating_expenses_annual: number;
  capex_reserve_annual: number;
  purchase_costs: number;
  exit_cap_rate: number;
  holding_period_years: number;
}

export interface DebtInput {
  loan_amount: number;
  interest_rate: number;
  amortization_years: number;
  term_years: number;
  interest_only_years: number;
  points_or_fees: number;
}

export interface ReitInput {
  property_nav: number;
  net_debt: number;
  shares_outstanding: number;
  share_price: number;
  funds_from_operations: number;
  dividend_per_share: number;
}

export interface RealEstateAnalysisRequest {
  property: PropertyInput;
  debt: DebtInput;
  reit: ReitInput;
  selling_cost_rate: number;
}

export interface SampleResponse {
  request: RealEstateAnalysisRequest;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface PropertySummary {
  property_name: string;
  property_type: string;
  market: string;
  purchase_price: number;
  purchase_costs: number;
  initial_equity: number;
  holding_period_years: number;
  loan_to_value: number;
}

export interface IncomeStatement {
  gross_rent: number;
  vacancy_loss: number;
  other_income: number;
  effective_gross_income: number;
  operating_expenses: number;
  net_operating_income: number;
  capex_reserve: number;
  noi_after_reserves: number;
}

export interface Valuation {
  net_operating_income: number;
  in_place_cap_rate: number;
  exit_cap_rate: number;
  purchase_price: number;
  value_at_exit_cap: number;
}

export interface DebtMetrics {
  loan_amount: number;
  loan_to_value: number;
  interest_rate: number;
  amortization_years: number;
  term_years: number;
  monthly_payment: number;
  annual_debt_service: number;
  dscr: number;
  remaining_balance_at_exit: number;
}

export interface AmortRow {
  month: number;
  payment: number;
  interest: number;
  principal: number;
  balance: number;
}

export interface LeveredReturns {
  initial_equity: number;
  year1_before_tax_cash_flow: number;
  cash_on_cash: number;
  exit_value: number;
  remaining_loan_balance: number;
  selling_costs: number;
  sale_proceeds: number;
  total_distributions: number;
  equity_multiple: number;
  irr?: number | null;
  irr_note?: string | null;
}

export interface CashFlowYear {
  year: number;
  effective_gross_income: number;
  net_operating_income: number;
  annual_debt_service: number;
  before_tax_cash_flow: number;
  equity_cash_flow: number;
}

export interface ScenarioResult {
  id: string;
  name: string;
  description: string;
  rent_growth_rate: number;
  vacancy_rate: number;
  exit_cap_rate: number;
  interest_rate: number;
  noi: number;
  dscr: number;
  cash_on_cash: number;
  exit_value: number;
  equity_multiple: number;
  irr?: number | null;
  notes: string[];
}

export interface ReitNavAnalysis {
  property_nav: number;
  net_debt: number;
  shares_outstanding: number;
  nav_per_share: number;
  share_price: number;
  premium_discount: number;
  ffo_per_share: number;
  p_ffo?: number | null;
  dividend_per_share: number;
  dividend_yield: number;
}

export interface RealEstateAnalysisResponse {
  data_status: "static_sample";
  property_summary: PropertySummary;
  income_statement: IncomeStatement;
  valuation: Valuation;
  debt_metrics: DebtMetrics;
  amortization_schedule: AmortRow[];
  levered_returns: LeveredReturns;
  cash_flow_projection: CashFlowYear[];
  scenario_results: ScenarioResult[];
  reit_nav_analysis: ReitNavAnalysis;
  notes: string[];
  disclaimer: string;
}

function backendUnavailable(): Error {
  return new Error(
    "Backend unavailable — start the QuantLab API to use the Real Estate Lab.",
  );
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
  return res.status >= 500 ? "Server error computing real-estate analytics." : `HTTP ${res.status}`;
}

/** GET /api/real-estate/sample */
export async function fetchRealEstateSample(signal?: AbortSignal): Promise<SampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/real-estate/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<SampleResponse>;
}

/** POST /api/real-estate/analyze */
export async function analyzeRealEstate(
  request: RealEstateAnalysisRequest,
  signal?: AbortSignal,
): Promise<RealEstateAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/real-estate/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<RealEstateAnalysisResponse>;
}

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //
export function money(value: number): string {
  return Math.round(value).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export function pct(value: number, digits = 2): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value: number, digits = 2): string {
  return value.toFixed(digits);
}
