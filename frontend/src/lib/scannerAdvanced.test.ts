import { Blob as NodeBlob } from "node:buffer";
import { describe, expect, it, vi } from "vitest";
import { declaredPValues, downloadScannerValidation, type ScannerValidationResponse } from "./scannerAdvanced";

describe("declared scanner p-value input", () => {
  it("retains the whole declared family and missing values", () => {
    expect(declaredPValues("")).toEqual([null, null, null]);
    expect(declaredPValues("0.01, 0.04, 0.20")).toEqual([.01, .04, .2]);
    expect(declaredPValues("0,1,0.5")).toEqual([0, 1, .5]);
  });
  it.each(["0.1,,0.3", "0.1,abc,0.2", "NaN,0.1,0.2", "0.1,0.2", "-1,0.1,0.2", "2,0.1,0.2"])("refuses %s", (text) => {
    expect(() => declaredPValues(text)).toThrow("three declared p-values");
  });
});

it("downloads retained material and caveats without mutating results", async () => {
  vi.useFakeTimers();
  vi.stubGlobal("Blob", NodeBlob);
  const create = vi.fn((_blob: Blob) => "blob:scanner-test");
  vi.stubGlobal("URL", Object.assign(class extends URL {}, { createObjectURL: create, revokeObjectURL: vi.fn() }));
  let filename = "";
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { filename = this.download; });
  const value = { schema_version: "scanner_validation_v1", result_fingerprint: "a".repeat(64),
    material: { pinned: "actual retained test material" }, caveats: ["Synthetic only; supplied p-values stay declared"] } as unknown as ScannerValidationResponse;
  const before = JSON.stringify(value);
  downloadScannerValidation(value);
  expect(filename).toBe("quantlab-scanner-validation-aaaaaaaaaaaa.json");
  const blob = create.mock.calls[0][0] as unknown as NodeBlob;
  expect(JSON.parse(await blob.text())).toEqual(value);
  expect(JSON.stringify(value)).toBe(before);
  vi.runAllTimers();
});
