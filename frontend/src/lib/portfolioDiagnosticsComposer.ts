import type { PortfolioRunCreate, PortfolioReturnInput } from "./portfolioDiagnostics";

export const MAX_IMPORT_BYTES = 2 * 1024 * 1024;
const ASSET_TYPES = ["equity", "futures", "crypto", "fx", "rates", "candidate", "index", "other"];
const length = (value: string) => Array.from(value).length;

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object.`);
  return value as Record<string, unknown>;
}

function fields(value: Record<string, unknown>, allowed: string[], label: string) {
  const extra = Object.keys(value).find((key) => !allowed.includes(key));
  if (extra !== undefined) throw new Error(`${label}: unsupported field ${extra}. Import return data only, not run configuration.`);
}

function text(value: unknown, label: string, max: number): string {
  if (typeof value !== "string" || !value.trim() || length(value.trim()) > max) {
    throw new Error(`${label} must contain 1 to ${max} characters after trimming.`);
  }
  return value.trim();
}

function calendarDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return year >= 1 && year <= 9999 && month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1];
}

export function parsePortfolioReturns(raw: string): PortfolioReturnInput {
  if (new TextEncoder().encode(raw).byteLength > MAX_IMPORT_BYTES) throw new Error("Return JSON exceeds the Composer limit of 2 MiB.");
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch { throw new Error("Invalid JSON. Supply frequency, timestamps and assets with aligned returns."); }
  const root = object(parsed, "Return data");
  fields(root, ["frequency", "timestamps", "assets"], "Return data");
  const frequency = text(root.frequency, "Declared frequency", 40);
  if (!Array.isArray(root.timestamps) || root.timestamps.length < 24 || root.timestamps.length > 2000) {
    throw new Error("Supply 24 to 2,000 shared timestamps.");
  }
  const timestamps: string[] = [];
  for (const date of root.timestamps) {
    if (!calendarDate(date)) throw new Error("Composer dates must be real calendar dates in exact YYYY-MM-DD format (years 0001-9999). Datetime/offset formats require the existing API.");
    if (timestamps.length && date <= timestamps[timestamps.length - 1]) throw new Error("Dates must be strictly increasing with no duplicates.");
    timestamps.push(date);
  }
  if (!Array.isArray(root.assets) || root.assets.length < 2 || root.assets.length > 20) throw new Error("Supply 2 to 20 assets.");
  const ids = new Set<string>();
  const groups = new Set<string>();
  const currencies = new Set<string>();
  const assets = root.assets.map((value, index) => {
    const source = object(value, `Asset ${index + 1}`);
    fields(source, ["asset_id", "returns", "name", "asset_type", "group", "currency"], `Asset ${index + 1}`);
    const asset_id = text(source.asset_id, "Asset ID", 64);
    if (ids.has(asset_id)) throw new Error(`Duplicate asset ID after trimming: ${asset_id}.`);
    ids.add(asset_id);
    if (!Array.isArray(source.returns) || source.returns.length !== timestamps.length) throw new Error(`Returns for ${asset_id} must align exactly with all ${timestamps.length} timestamps.`);
    const returns = source.returns.map((v) => {
      if (typeof v !== "number" || !Number.isFinite(v)) throw new Error(`Returns for ${asset_id} must be finite JSON numbers, not strings, booleans or null.`);
      return v;
    });
    const asset: PortfolioReturnInput["assets"][number] = { asset_id, returns };
    if (Object.hasOwn(source, "name")) {
      if (source.name !== null && (typeof source.name !== "string" || length(source.name) > 200)) throw new Error(`Name for ${asset_id} must be null or a string of at most 200 characters.`);
      asset.name = source.name as string | null;
    }
    if (Object.hasOwn(source, "asset_type")) {
      if (typeof source.asset_type !== "string" || !ASSET_TYPES.includes(source.asset_type)) throw new Error(`Unsupported asset_type for ${asset_id}.`);
      asset.asset_type = source.asset_type as NonNullable<typeof asset.asset_type>;
    }
    if (Object.hasOwn(source, "group")) {
      if (source.group !== null && (typeof source.group !== "string" || length(source.group) > 64)) throw new Error(`Group for ${asset_id} must be null or a string of at most 64 characters.`);
      asset.group = source.group === null ? null : text(source.group, "Group", 64);
      if (asset.group !== null) groups.add(asset.group);
    }
    if (Object.hasOwn(source, "currency")) {
      if (source.currency !== null && (typeof source.currency !== "string" || length(source.currency) > 8)) throw new Error(`Currency for ${asset_id} must be null or a string of at most 8 characters.`);
      asset.currency = source.currency === null ? null : text(source.currency, "Currency", 8).toUpperCase();
      if (asset.currency !== null && length(asset.currency) > 8) throw new Error(`Currency for ${asset_id} must remain within 8 characters after uppercasing.`);
      if (asset.currency !== null) currencies.add(asset.currency);
    }
    return asset;
  });
  if (groups.size > 8) throw new Error("At most 8 distinct groups are supported.");
  if (currencies.size > 1) throw new Error("Declare at most one currency; no currency conversion is performed.");
  return { frequency, timestamps, assets };
}

export const weightText = (values: Record<string, string>, id: string): string => Object.hasOwn(values, id) ? values[id] : "";

function decimal(raw: string, label: string): number {
  if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(raw.trim()) || !Number.isFinite(Number(raw))) {
    throw new Error(`${label} must be an explicit finite number; blank is not zero.`);
  }
  return Number(raw);
}

export function enteredWeightTotal(data: PortfolioReturnInput, values: Record<string, string>): number | null {
  try { return data.assets.reduce((sum, asset) => sum + decimal(weightText(values, asset.asset_id), "Weight"), 0); }
  catch { return null; }
}

export function buildPortfolioRun(data: PortfolioReturnInput, nameRaw: string, values: Record<string, string>, lookbackRaw: string): PortfolioRunCreate {
  const name = text(nameRaw, "Run name", 200);
  const maximum = Math.min(500, data.timestamps.length - 1);
  if (!/^\d+$/.test(lookbackRaw.trim()) || Number(lookbackRaw) < 3 || Number(lookbackRaw) > maximum) throw new Error(`Lookback must be an integer from 3 to ${maximum}.`);
  const lookback = Number(lookbackRaw);
  const entries = data.assets.map(({ asset_id }) => {
    const percent = decimal(weightText(values, asset_id), `Weight for ${asset_id}`);
    if (percent < 0 || percent > 100) throw new Error(`Weight for ${asset_id} must be between 0% and 100%.`);
    return [asset_id, percent / 100] as const;
  });
  if (Math.abs(entries.reduce((sum, [, weight]) => sum + weight, 0) - 1) > 1e-6) throw new Error("Weights must total 100% within 0.0001 percentage points. No normalization is applied.");
  return { ...data, name, weights: Object.fromEntries(entries), method: "user_supplied", normalization: "none",
    weight_provenance: { basis: "declared" }, covariance: { method: "sample", repair: "none" },
    estimation: { mode: "rolling", lookback, lag: 1 },
    constraints: { long_only: true, min_weight: 0, max_weight: 1, net_exposure_target: 1, gross_exposure_limit: 1, cash_residual_allowed: false },
    rebalance: { kind: "one_time", initial_turnover_policy: "none" } };
}
