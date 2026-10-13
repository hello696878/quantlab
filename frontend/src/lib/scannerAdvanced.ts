import type { ScannerRequest, ScannerStrategy } from "./types";

export interface NeutralisationPolicy {
  schema_version?: "scanner_neutralisation_v1";
  mode: "dollar" | "sector" | "beta";
  missing?: "exclude" | "refuse";
  failed_rebalance?: "cash";
  gross_cap?: number;
  beta_window?: number;
  beta_min_observations?: number;
  volatility?: { target: number; window?: number; min_observations?: number; periods_per_year?: 252 } | null;
}
export interface ScannerInputs {
  schema_version?: "scanner_declarations_v1";
  source?: "time_varying_declared";
  exposures?: { asset_id: string; period: string; available_at: string; sector?: string | null;
    beta?: number | null; eligible: boolean; liquidity: number }[] | null;
  factor_returns?: { period: string; available_at: string; value: number }[] | null;
}
export interface ScannerExposure {
  net: number; gross: number; sectors: Record<string, number>; beta: number | null;
}
export interface ScannerRebalance {
  date: string; status: string; reason: string | null; eligible_count: number;
  excluded: { asset_id: string; reason: string }[];
  rank: number | null; columns: number | null; condition_number: number | null;
  reconstruction_error: number | null; support_rank: number | null;
  raw: ScannerExposure; transformed: ScannerExposure; neutral: ScannerExposure; final: ScannerExposure;
  volatility_estimate: number | null; volatility_target: number | null; volatility_scale: number | null;
  achieved_ex_ante: number | null; cap_binding: boolean; constraint_error: number;
  outcome_date: string | null; turnover: number; cost: number; gross_return: number; net_return: number;
}
export interface AdvancedScannerResult {
  policy: NeutralisationPolicy; input_fingerprint: string; exposure_provenance: string; factor_provenance: string;
  timing: string; support_policy: string; failed_rebalance: string; diagnostics: ScannerRebalance[];
  total_rebalances: number; diagnostics_truncated: boolean;
  latest_scores: { asset_id: string; raw_score: number | null; transformed_score: number | null; weight: number;
    sector?: string | null; beta?: number | null }[];
  realized_net_volatility: number; caveats: string[];
}
export interface ScannerCandidate {
  candidate_id: string; strategy: ScannerStrategy; policy: NeutralisationPolicy; raw_p_value: number | null;
  p_value_source?: string; hypothesis?: string; p_value_scope?: "declared_external" | "this_scanner_sample";
}
export interface ScannerValidationRequest {
  scanner: ScannerRequest; candidates: ScannerCandidate[]; n_folds: number; embargo_days: number; alpha: number;
}
export interface ScannerCorrection {
  candidate_id: string; raw_p_value: number | null; bonferroni: number | null; holm: number | null; bh: number | null;
  provenance_status: "declared" | "unavailable" | "invalid"; provenance: Record<string, unknown> | null;
  state_raw: string; state_bonferroni: string; state_holm: string; state_bh: string;
}
export interface ScannerValidationResponse {
  schema_version: "scanner_validation_v1"; input_fingerprint: string; family_fingerprint: string;
  result_fingerprint: string; split_configuration_fingerprint: string;
  samples: Record<string, unknown>[];
  folds: { label: string; train_ids: string[]; test_ids: string[]; purged_ids: string[]; embargoed_ids: string[];
    fingerprint: string; trained_parameters: string[]; training_used_for_fit: boolean;
    audit: { valid: boolean; remaining_overlap_count: number; train_count: number; test_count: number;
      purged_count: number; embargoed_count: number; [key: string]: unknown } }[];
  candidates: { candidate_id: string; status: "available" | "unavailable"; reason: string | null;
    mean_test_net_return: number | null; outcomes: Record<string, unknown>[]; correction: ScannerCorrection }[];
  family: { declared_count: number; included_count: number; missing_ids: string[]; invalid_ids: string[];
    alpha: number; methods: string[]; provenance: string; invalid_policy: string };
  material: Record<string, unknown>; caveats: string[]; unavailable_statistics: Record<string, string>;
  conventions: Record<string, unknown>;
}

export function declaredPValues(text: string): (number | null)[] {
  if (!text.trim()) return [null, null, null];
  const tokens = text.split(",").map((v) => v.trim());
  if (tokens.length !== 3 || tokens.some((v) => !/^(?:0(?:\.\d+)?|1(?:\.0+)?)$/.test(v))) {
    throw new Error("Enter three declared p-values in [0, 1], or leave the entire field empty.");
  }
  return tokens.map(Number);
}

export function downloadScannerValidation(result: ScannerValidationResponse): void {
  const blob = new Blob([JSON.stringify(result, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `quantlab-scanner-validation-${result.result_fingerprint.slice(0, 12)}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
