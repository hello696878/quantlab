/**
 * Shared helpers for QuantLab component tests (Phase 63.0).
 *
 * Thin on purpose: the app renders its workspaces without React context
 * providers, so `render` from React Testing Library is used directly.  What
 * lives here is the setup that is easy to get subtly wrong — user-event wiring,
 * localStorage failure simulation, and clipboard doubles — so every test
 * expresses the same intent the same way.
 */

import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { vi } from "vitest";

/** Render + a `userEvent` session bound to the same document. */
export function renderWithUser(
  ui: ReactElement,
  options?: RenderOptions,
): RenderResult & { user: ReturnType<typeof userEvent.setup> } {
  const user = userEvent.setup();
  return { user, ...render(ui, options) };
}

/**
 * Replace `navigator.clipboard` for one test.
 *
 * `mode: "ok"` resolves, `"reject"` rejects (permission denied), and
 * `"absent"` removes the API entirely (older/locked-down browsers) so the
 * component's documented fallback path can be asserted.
 *
 * IMPORTANT ordering: call this AFTER `renderWithUser`. `userEvent.setup()`
 * installs its own clipboard stub, so stubbing first would be overwritten and
 * the test would silently assert against user-event's stub instead of yours.
 */
export function stubClipboard(mode: "ok" | "reject" | "absent"): {
  writeText: ReturnType<typeof vi.fn<(text: string) => Promise<void>>>;
} {
  const writeText = vi.fn((_text: string) =>
    mode === "reject"
      ? Promise.reject(new Error("clipboard write denied"))
      : Promise.resolve(),
  );
  Object.defineProperty(window.navigator, "clipboard", {
    configurable: true,
    value: mode === "absent" ? undefined : { writeText },
  });
  return { writeText };
}

/**
 * Make `window.localStorage` behave like a browser that refuses storage
 * (Safari private mode, disabled site data): every accessor throws.
 */
export function stubUnavailableLocalStorage(): void {
  const throwing = {
    getItem() {
      throw new Error("localStorage is unavailable");
    },
    setItem() {
      throw new Error("localStorage is unavailable");
    },
    removeItem() {
      throw new Error("localStorage is unavailable");
    },
    clear() {
      throw new Error("localStorage is unavailable");
    },
    key() {
      throw new Error("localStorage is unavailable");
    },
    length: 0,
  } satisfies Storage;
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: throwing,
  });
}
