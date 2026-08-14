/**
 * Vitest global setup (Phase 63.0).
 *
 * Provides the narrow browser-API shims jsdom lacks, plus a hard network
 * guard.  Deliberate non-goals of this file:
 *
 * * it never silences React errors or warnings — a component that logs a real
 *   React error must still be visible to the person running the tests;
 * * it never mocks `fetch` to succeed.  An unmocked request FAILS the test so
 *   a missing API mock can never pass silently;
 * * it never stubs application modules.  Tests inject their own doubles.
 *
 * Individual tests may override any shim locally (and `restoreMocks` in
 * vitest.config.ts puts it back afterwards).
 */

import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, expect, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// ---------------------------------------------------------------------------
// Network guard — unmocked requests fail loudly
// ---------------------------------------------------------------------------

/**
 * Component tests must never touch a real backend or the network.  Any code
 * path that reaches `fetch` without a test-supplied double is a defect in the
 * test (a missing mock), so it throws instead of hanging or silently passing.
 */
function networkGuard(input: unknown): never {
  const target =
    typeof input === "string"
      ? input
      : input && typeof input === "object" && "url" in input
        ? String((input as { url: unknown }).url)
        : String(input);
  throw new Error(
    `Unmocked network request to "${target}" in a component test. ` +
      "Component tests are offline by design: mock the specific local API " +
      "client module (e.g. vi.mock(\"@/lib/api\")) and return deterministic " +
      "repository-owned data. See docs/FRONTEND_COMPONENT_TESTING.md.",
  );
}

// ---------------------------------------------------------------------------
// Browser APIs jsdom does not implement
// ---------------------------------------------------------------------------

class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

function installBrowserShims(): void {
  vi.stubGlobal("fetch", vi.fn(networkGuard));

  if (!window.matchMedia) {
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    );
  }

  if (!window.ResizeObserver) {
    vi.stubGlobal("ResizeObserver", ResizeObserverStub);
  }

  // jsdom has no layout engine; components that scroll a row into view must
  // not crash the test.
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn();
  }

  // requestAnimationFrame exists in modern jsdom, but keep the fallback so the
  // suite does not depend on the jsdom version.
  if (!window.requestAnimationFrame) {
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) =>
      setTimeout(() => cb(performance.now()), 0) as unknown as number,
    );
    vi.stubGlobal("cancelAnimationFrame", (id: number) => clearTimeout(id));
  }
}

beforeEach(() => {
  installBrowserShims();
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

// ---------------------------------------------------------------------------
// Numeric honesty matcher (shared repository convention)
// ---------------------------------------------------------------------------

expect.extend({
  /**
   * Rejects NaN / Infinity in rendered numeric text — the same honesty rule
   * the backend labs and Playwright specs enforce.
   */
  toBeFiniteNumericText(received: string | null | undefined) {
    const text = String(received ?? "");
    const offending = /\bNaN\b|\bInfinity\b|\b-Infinity\b/.exec(text);
    return {
      pass: offending === null,
      message: () =>
        offending === null
          ? `expected "${text}" to contain NaN or Infinity`
          : `rendered text contains ${offending[0]}: "${text}"`,
    };
  },
});

declare module "vitest" {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface Assertion<T = any> {
    toBeFiniteNumericText(): T;
  }
  interface AsymmetricMatchersContaining {
    toBeFiniteNumericText(): unknown;
  }
}
