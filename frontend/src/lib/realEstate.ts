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
// Mortgage & MBS prepayment (Phase 22.1)
// --------------------------------------------------------------------------- //
export type PrepaymentModel = "constant_cpr" | "psa";

export interface MortgagePoolInput {
  pool_name: string;
  original_balance: number;
  current_balance: number;
  coupon_rate: number;
  servicing_fee_rate: number;
  remaining_term_months: number;
  seasoning_months: number;
  wam_months?: number | null;
  wala_months?: number | null;
}

export interface PrepaymentInput {
  model: PrepaymentModel;
  cpr?: number | null;
  psa_speed?: number | null;
  prepayment_lag_months: number;
}

export interface ValuationInput {
  discount_rate: number;
  price?: number | null;
  rate_shock_bps: number;
  prepayment_stress_multiplier: number;
}

export interface MortgageMbsRequest {
  pool: MortgagePoolInput;
  prepayment: PrepaymentInput;
  valuation: ValuationInput;
}

export interface MbsSampleResponse {
  request: MortgageMbsRequest;
  data_status: "static_sample";
  disclaimer: string;
  notes: string[];
}

export interface PoolSummary {
  pool_name: string;
  original_balance: number;
  current_balance: number;
  pool_factor: number;
  coupon_rate: number;
  servicing_fee_rate: number;
  net_coupon: number;
  remaining_term_months: number;
  seasoning_months: number;
}

export interface PrepaymentAssumption {
  model: PrepaymentModel;
  cpr?: number | null;
  psa_speed?: number | null;
  prepayment_lag_months: number;
  prepayment_stress_multiplier: number;
}

export interface ValuationAssumption {
  discount_rate: number;
  net_coupon: number;
  price?: number | null;
}

export interface MbsCashFlowSummary {
  num_months: number;
  total_interest: number;
  total_scheduled_principal: number;
  total_prepayment: number;
  total_principal: number;
  total_cash_flow: number;
  final_balance: number;
}

export interface MbsCashFlowRow {
  month: number;
  beginning_balance: number;
  scheduled_principal: number;
  prepayment_principal: number;
  interest: number;
  total_cash_flow: number;
  ending_balance: number;
}

export interface PsaPathPoint {
  month: number;
  pool_age_month: number;
  cpr: number;
  smm: number;
}

export interface DurationConvexity {
  shock_bps: number;
  price_base: number;
  price_up: number;
  price_down: number;
  duration: number;
  convexity: number;
  yield_estimate?: number | null;
}

export interface MbsScenarioResult {
  id: string;
  name: string;
  description: string;
  price_100: number;
  wal: number;
  duration: number;
  convexity: number;
  total_interest: number;
  total_principal: number;
  final_balance: number;
  notes: string[];
}

export interface MortgageMbsAnalysisResponse {
  data_status: "static_sample";
  pool_summary: PoolSummary;
  prepayment_assumption: PrepaymentAssumption;
  valuation_assumption: ValuationAssumption;
  price: number;
  price_100: number;
  wal: number;
  cash_flow_summary: MbsCashFlowSummary;
  cash_flow_schedule: MbsCashFlowRow[];
  psa_path: PsaPathPoint[];
  duration_convexity: DurationConvexity;
  scenario_results: MbsScenarioResult[];
  notes: string[];
  disclaimer: string;
}

/** GET /api/real-estate/mbs/sample */
export async function fetchMbsSample(signal?: AbortSignal): Promise<MbsSampleResponse> {
  let res: Response;
  try {
    res = await fetch("/api/real-estate/mbs/sample", { signal, headers: { Accept: "application/json" } });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<MbsSampleResponse>;
}

/** POST /api/real-estate/mbs/analyze */
export async function analyzeMbs(
  request: MortgageMbsRequest,
  signal?: AbortSignal,
): Promise<MortgageMbsAnalysisResponse> {
  let res: Response;
  try {
    res = await fetch("/api/real-estate/mbs/analyze", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw backendUnavailable();
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<MortgageMbsAnalysisResponse>;
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
