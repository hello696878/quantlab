import { expect, expectTypeOf, it } from "vitest";
import type { PortfolioRunCreate } from "./portfolioDiagnostics";
import { buildPortfolioRun, enteredWeightTotal, MAX_IMPORT_BYTES, parsePortfolioReturns, preparePortfolioReuse, weightText } from "./portfolioDiagnosticsComposer";
import { constructionInput, diagnosticRun, returnInput, storedUniverse } from "@/test/fixtures/portfolioDiagnosticsComposer";

const parse = (value: unknown) => parsePortfolioReturns(JSON.stringify(value));

it("preserves imported order and numbers and assembles the exact bounded contract", () => {
  const data = parse({ ...returnInput(), assets: returnInput().assets.map((a) => ({ ...a, name: a.asset_id, group: "g", currency: "usd", asset_type: "index" })) });
  const result = buildPortfolioRun(data, "  Explicit book  ", { a: "70", b: "30" }, "20");
  expect(result).toEqual({ ...data, name: "Explicit book", method: "user_supplied", weights: { a: 0.7, b: 0.3 }, normalization: "none",
    weight_provenance: { basis: "declared" }, covariance: { method: "sample", repair: "none" },
    estimation: { mode: "rolling", lookback: 20, lag: 1 },
    constraints: { long_only: true, min_weight: 0, max_weight: 1, net_exposure_target: 1, gross_exposure_limit: 1, cash_residual_allowed: false },
    rebalance: { kind: "one_time", initial_turnover_policy: "none" } });
  expect(data.assets[0].returns).toEqual(returnInput().assets[0].returns);
  expect(data.assets.map((a) => a.asset_id)).toEqual(["a", "b"]);
  expect(data.assets[0].currency).toBe("USD");
});

it.each([24, 2000])("accepts observation boundary %i", (n) => expect(parse(returnInput(n)).timestamps).toHaveLength(n));
it.each([2, 20])("accepts asset boundary %i", (n) => expect(parse(returnInput(24, Array.from({ length: n }, (_, i) => `a${i}`))).assets).toHaveLength(n));
it.each([23, 2001])("rejects observation boundary %i", (n) => expect(() => parse(returnInput(n))).toThrow(/24 to/));
it.each([1, 21])("rejects asset boundary %i", (n) => expect(() => parse(returnInput(24, Array.from({ length: n }, (_, i) => `a${i}`)))).toThrow(/2 to 20/));
it.each(["{", "null", "[]", "true"])("rejects malformed/root JSON %s", (raw) => expect(() => parsePortfolioReturns(raw)).toThrow());
it.each(["metadata", "weights", "dataset_version_id", "weight_provenance", "estimation", "__proto__"])("rejects root injection %s", (key) => {
  expect(() => parse({ ...returnInput(), [key]: {} })).toThrow(/unsupported field/);
});
it.each(["metadata", "integer_lots", "formula"])("rejects asset field %s", (key) => {
  const data = returnInput(); Object.assign(data.assets[0], { [key]: {} }); expect(() => parse(data)).toThrow(/unsupported field/);
});
it.each(["0.1", true, null])("rejects non-number return %s", (value) => {
  const data = returnInput(); (data.assets[0].returns as unknown[])[0] = value; expect(() => parse(data)).toThrow(/finite JSON numbers/);
});
it("rejects overflow JSON numbers and nonfinite tokens", () => {
  expect(() => parsePortfolioReturns(JSON.stringify(returnInput()).replace("-0.005", "1e400"))).toThrow(/finite JSON numbers/);
  expect(() => parsePortfolioReturns(JSON.stringify(returnInput()).replace("-0.005", "NaN"))).toThrow(/Invalid JSON/);
});
it("rejects misalignment, duplicate trimmed IDs and blank/long IDs", () => {
  const data = returnInput(); data.assets[0].returns.pop(); expect(() => parse(data)).toThrow(/align exactly/);
  for (const ids of [["a", " a "], ["", "b"], ["a".repeat(65), "b"]]) expect(() => parse(returnInput(24, ids))).toThrow();
  expect(parse(returnInput(24, [" a ", "b"])).assets[0].asset_id).toBe("a");
});
it.each(["2023-02-29", "1900-02-29", "0000-01-01", "2024-04-31", "2024-00-01", "2024-13-01", "2024-01-00", "2024-1-01", "2024-01-01T00:00:00Z", "2024-01-01+00:00"])("rejects invalid/unsupported date %s", (value) => {
  const data = returnInput(); data.timestamps[0] = value; expect(() => parse(data)).toThrow(/YYYY-MM-DD/);
});
it("accepts leap years and dates at the supported year limits without JS normalization", () => {
  const data = returnInput(); data.timestamps[0] = "0001-01-01"; data.timestamps[1] = "2000-02-29"; data.timestamps[23] = "9999-12-31";
  expect(parse(data).timestamps).toEqual(data.timestamps);
  const leap = returnInput(); leap.timestamps = Array.from({ length: 24 }, (_, i) => `2024-02-${String(i + 6).padStart(2, "0")}`);
  expect(parse(leap).timestamps.at(-1)).toBe("2024-02-29");
});
it.each(["2024-01-01", "2023-12-31"])("rejects duplicate/out-of-order date %s", (value) => {
  const data = returnInput(); data.timestamps[1] = value; expect(() => parse(data)).toThrow(/strictly increasing/);
});
it("enforces UTF-8 2 MiB limit before parsing", () => {
  expect(() => parsePortfolioReturns(" ".repeat(MAX_IMPORT_BYTES + 1))).toThrow(/2 MiB/);
  expect(() => parsePortfolioReturns("\u4e00".repeat(MAX_IMPORT_BYTES / 2))).toThrow(/2 MiB/);
});
it.each([{ name: "n".repeat(201) }, { name: 3 }, { asset_type: "unknown" }, { group: "" }, { group: "g".repeat(65) }, { currency: "" }, { currency: "123456789" }, { currency: "\u00df".repeat(5) }])("rejects invalid metadata %o", (metadata) => {
  const data = returnInput(); Object.assign(data.assets[0], metadata); expect(() => parse(data)).toThrow();
});
it("enforces declared currency/group limits, and permits nullable metadata", () => {
  const data = returnInput(24, Array.from({ length: 9 }, (_, i) => `a${i}`));
  data.assets.forEach((a, i) => Object.assign(a, { group: `g${i}` })); expect(() => parse(data)).toThrow(/8 distinct groups/);
  const mixed = returnInput(); Object.assign(mixed.assets[0], { currency: "USD" }); Object.assign(mixed.assets[1], { currency: "EUR" }); expect(() => parse(mixed)).toThrow(/one currency/);
  Object.assign(mixed.assets[1], { currency: null, group: null, name: null }); expect(parse(mixed).assets[1].name).toBeNull();
});
it("keeps zero explicit, rejects blank/invalid weights and never normalizes", () => {
  const data = parse(returnInput());
  expect(buildPortfolioRun(data, "Zero", { a: "0.", b: "100" }, "3").weights).toEqual({ a: 0, b: 1 });
  for (const a of ["", " ", "NaN", "Infinity", "0x10", "20abc", "-1", "101"]) expect(() => buildPortfolioRun(data, "Test", { a, b: "30" }, "20")).toThrow();
  expect(() => buildPortfolioRun(data, "Test", { a: "50", b: "49.9998" }, "20")).toThrow(/total 100/);
  expect(enteredWeightTotal(data, { a: "50", b: "49.9998" })).toBe(99.9998);
  expect(enteredWeightTotal(data, { a: "", b: "100" })).toBeNull();
  expect(buildPortfolioRun(data, "Tolerance", { a: "50", b: "49.99995" }, "20").weights.b).toBe(0.4999995);
});
it.each(["", "2", "24", "20.5", "1e1", "-3", "501"])("rejects lookback %s", (value) => expect(() => buildPortfolioRun(parse(returnInput()), "Test", { a: "70", b: "30" }, value)).toThrow(/Lookback/));
it("bounds lookback by observations and 500; validates name", () => {
  expect(buildPortfolioRun(parse(returnInput(501)), "Max", { a: "70", b: "30" }, "500").estimation.lookback).toBe(500);
  for (const name of [" ", "n".repeat(201)]) expect(() => buildPortfolioRun(parse(returnInput()), name, { a: "70", b: "30" }, "20")).toThrow(/Run name/);
});
it("handles prototype-named assets with own-property-safe maps", () => {
  const data = parse(returnInput(24, ["constructor", "toString", "__proto__"]));
  expect(weightText({}, "constructor")).toBe("");
  expect(() => buildPortfolioRun(data, "Prototype book", {}, "20")).toThrow(/explicit finite/);
  const weights = Object.fromEntries([["constructor", "70"], ["toString", "0"], ["__proto__", "30"]]);
  const payload = buildPortfolioRun(data, "Prototype book", weights, "20");
  expect(Object.keys(payload.weights)).toEqual(["constructor", "toString", "__proto__"]);
  expect(payload.weights.__proto__).toBe(0.3);
  expect(JSON.parse(JSON.stringify(payload)).weights).toEqual(payload.weights);
});

it.each(["equal_weight", "inverse_volatility"] as const)("builds %s without manual fields or a volatility floor", (method) => {
  const data = parse(returnInput());
  const payload = buildPortfolioRun(data, "Derived", { a: "invalid", b: "" }, "20", method);
  const manual = buildPortfolioRun(data, "Derived", { a: "70", b: "30" }, "20");
  const { weights: _weights, weight_provenance: _provenance, ...common } = manual;
  expect(payload).toEqual({ ...common, method, normalization: "sum_to_one" });
  for (const key of ["weights", "weight_provenance", "volatility_floor"]) expect(Object.hasOwn(JSON.parse(JSON.stringify(payload)), key)).toBe(false);
  expect(data).toEqual(parse(returnInput()));
  expect(() => buildPortfolioRun(data, "", {}, "20", method)).toThrow(/Run name/);
  expect(() => buildPortfolioRun(data, "Derived", {}, "24", method)).toThrow(/Lookback/);
});

it("excludes manual-only fields from the derived request type", () => {
  type Derived = Extract<PortfolioRunCreate, { normalization: "sum_to_one" }>;
  expectTypeOf<Derived["weights"]>().toEqualTypeOf<undefined>();
  expectTypeOf<Derived["weight_provenance"]>().toEqualTypeOf<undefined>();
  expectTypeOf<PortfolioRunCreate["volatility_floor"]>().toEqualTypeOf<undefined>();
});

it("projects actual stored return data exactly, in supplied order, into an independent validated snapshot", () => {
  const input = constructionInput(); input.assets.reverse();
  const universe = storedUniverse(input);
  universe.assets[0].name = "  Preserved source name  "; universe.assets[0].currency = "USD";
  const source = diagnosticRun({ universe });
  const before = structuredClone(source);
  const draft = preparePortfolioReuse(source, 51);
  expect(draft.sourceId).toBe(51); expect(draft.sourceName).toBe(source.name);
  expect(draft.data).toEqual({ frequency: "daily", timestamps: universe.timestamps,
    assets: universe.assets.map(({ integer_lots: _lots, metadata: _metadata, ...asset }) => asset) });
  expect(draft.data.assets.map((a) => a.asset_id)).toEqual(["b", "a"]);
  expect(draft.data.assets[0].returns).toEqual(input.assets[0].returns);
  expect(JSON.parse(draft.raw)).toEqual(draft.data);
  expect(parsePortfolioReturns(draft.raw)).toEqual(draft.data);
  expect(draft.data.timestamps).not.toBe(universe.timestamps);
  expect(draft.data.assets[0].returns).not.toBe(universe.assets[0].returns);
  draft.data.assets[0].returns[0] = 0.9; draft.data.timestamps[0] = "2000-01-01";
  expect(source).toEqual(before);
});

it.each(["user_supplied", "equal_weight", "inverse_volatility", "erc", "min_variance", "future_method"])("does not whitelist source method %s or require successful construction", (method) => {
  const source = diagnosticRun({ method, solver_status: "failed", result_fingerprint: null });
  expect(preparePortfolioReuse(source, 51).data.assets[0].returns).toEqual(source.universe.assets[0].returns);
});

it.each(["pending", "running", "failed", "invalidated"] as const)("refuses parent state %s", (status) => {
  expect(() => preparePortfolioReuse(diagnosticRun({ status }), 51)).toThrow(/only for completed/);
});
it.each([0, -1, 1.5, NaN, Number.MAX_SAFE_INTEGER + 1])("refuses malformed source identity %s", (id) => {
  expect(() => preparePortfolioReuse(diagnosticRun({ id }), id)).toThrow(/positive source ID/);
});
it("refuses a stored identity that does not match the viewed source", () => {
  expect(() => preparePortfolioReuse(diagnosticRun(), 52)).toThrow(/matching the viewed run/);
});

const sourceLinks = ["dataset_version_id", "validation_run_id", "regime_run_id", "regime_definition_id", "cost_diagnostic_run_id", "overfitting_run_id", "experiment_id"];
it.each(sourceLinks)("rejects any non-null %s, including falsy malformed links", (key) => {
  for (const value of [1, 0, false, "", undefined]) {
    const source = diagnosticRun(); Object.assign(source, { [key]: value });
    expect(() => preparePortfolioReuse(source, 51)).toThrow(key);
  }
});
it("allows absent source links and neutral stored extras", () => {
  const source = diagnosticRun();
  sourceLinks.forEach((key) => Reflect.deleteProperty(source, key));
  for (const key of ["benchmark_returns", "prior_weights", "sample_ids"]) Reflect.deleteProperty(source.universe, key);
  source.universe.assets.forEach((a) => { Reflect.deleteProperty(a, "integer_lots"); Reflect.deleteProperty(a, "metadata"); });
  source.configuration = {};
  expect(preparePortfolioReuse(source, 51).data.assets).toHaveLength(2);
});
it.each(["benchmark_returns", "prior_weights", "sample_ids"])("does not silently discard non-neutral %s", (key) => {
  for (const value of [[], {}, 0, false, "", undefined]) {
    const source = diagnosticRun(); Object.assign(source.universe, { [key]: value });
    expect(() => preparePortfolioReuse(source, 51)).toThrow(key);
  }
});
it("refuses meaningful or malformed asset extras", () => {
  for (const value of [true, 0, null, "false", undefined]) {
    const source = diagnosticRun(); Object.assign(source.universe.assets[0], { integer_lots: value });
    expect(() => preparePortfolioReuse(source, 51)).toThrow(/integer_lots/);
  }
  for (const value of [{ provider: "source" }, [], null, false, 0, "", undefined]) {
    const source = diagnosticRun(); Object.assign(source.universe.assets[0], { metadata: value });
    expect(() => preparePortfolioReuse(source, 51)).toThrow(/metadata/);
  }
});
it("refuses linked fingerprints and validation split labels rather than stripping provenance", () => {
  for (const value of [{ dataset: "fingerprint" }, null, [], 0, false, undefined]) {
    const source = diagnosticRun(); source.configuration.linked_fingerprints = value;
    expect(() => preparePortfolioReuse(source, 51)).toThrow(/linked_fingerprints/);
  }
  for (const value of ["train", "", false, 0, undefined]) {
    const source = diagnosticRun(); source.configuration.validation_split_label = value;
    expect(() => preparePortfolioReuse(source, 51)).toThrow(/validation_split_label/);
  }
});
it.each(["prices", "weights", "__proto__"])("refuses unknown stored fields %s", (key) => {
  const universeExtra = diagnosticRun(); universeExtra.universe = { ...universeExtra.universe, [key]: [] };
  expect(() => preparePortfolioReuse(universeExtra, 51)).toThrow(/unsupported field/);
  const assetExtra = diagnosticRun(); assetExtra.universe.assets[0] = { ...assetExtra.universe.assets[0], [key]: 0 };
  expect(() => preparePortfolioReuse(assetExtra, 51)).toThrow(/unsupported field/);
});
it("explicitly refuses missing return arrays, datetime timestamps and malformed values", () => {
  const missing = diagnosticRun(); Reflect.deleteProperty(missing.universe.assets[0], "returns");
  expect(() => preparePortfolioReuse(missing, 51)).toThrow(/returns must be an array/);
  const datetime = diagnosticRun(); datetime.universe.timestamps[0] += "T00:00:00Z";
  expect(() => preparePortfolioReuse(datetime, 51)).toThrow(/YYYY-MM-DD/);
  for (const value of ["0.01", NaN, Infinity, null, true]) {
    const source = diagnosticRun(); Object.assign(source.universe.assets[0].returns, { 0: value });
    expect(() => preparePortfolioReuse(source, 51)).toThrow(/finite JSON numbers/);
  }
});
it("refuses normalization of stored frequency, identifiers, groups and currency", () => {
  const frequency = diagnosticRun(); frequency.universe.frequency = " daily ";
  expect(() => preparePortfolioReuse(frequency, 51)).toThrow(/normalization/);
  for (const fields of [{ asset_id: " a " }, { group: " g " }, { currency: "usd" }, { name: undefined }]) {
    const source = diagnosticRun(); Object.assign(source.universe.assets[0], fields);
    expect(() => preparePortfolioReuse(source, 51)).toThrow(/normalization/);
  }
  const signedZero = diagnosticRun(); signedZero.universe.assets[0].returns[0] = -0;
  expect(() => preparePortfolioReuse(signedZero, 51)).toThrow(/change during serialization/);
});
it("applies the same import bounds and UTF-8 byte limit to the projected JSON", () => {
  for (const n of [23, 2001]) {
    const source = diagnosticRun({ universe: storedUniverse(returnInput(n)) });
    expect(() => preparePortfolioReuse(source, 51)).toThrow(/24 to 2,000/);
  }
  const large = diagnosticRun(); large.universe.assets[0].name = "\u4e00".repeat(MAX_IMPORT_BYTES / 2);
  expect(() => preparePortfolioReuse(large, 51)).toThrow(/2 MiB/);
});
