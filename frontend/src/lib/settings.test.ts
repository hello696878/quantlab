/**
 * Settings + browser-storage safety tests (Phase 63.0).
 *
 * The settings helper is the repository's shared localStorage pattern: it must
 * return defaults on the server, survive a browser that refuses storage, and
 * never let a malformed stored value reach the app as-is. These are the
 * failure modes that historically break hydration.
 */

import { describe, expect, it, vi } from "vitest";
import {
  DEFAULT_SETTINGS,
  SETTINGS_STORAGE_KEY,
  loadSettings,
  resetSettings,
  sanitizeSettings,
  saveSettings,
} from "@/lib/settings";
import { stubUnavailableLocalStorage } from "@/test/testUtils";

describe("sanitizeSettings", () => {
  it("returns the documented defaults for a completely invalid value", () => {
    expect(sanitizeSettings(null)).toEqual(DEFAULT_SETTINGS);
    expect(sanitizeSettings("not an object")).toEqual(DEFAULT_SETTINGS);
    expect(sanitizeSettings(42)).toEqual(DEFAULT_SETTINGS);
    expect(sanitizeSettings([])).toEqual(DEFAULT_SETTINGS);
  });

  it("keeps valid fields and replaces invalid ones with defaults", () => {
    const cleaned = sanitizeSettings({
      ...DEFAULT_SETTINGS,
      accent_color: "not-a-real-accent",
    });
    expect(cleaned.accent_color).toBe(DEFAULT_SETTINGS.accent_color);
  });

  it("never returns a non-finite number", () => {
    const cleaned = sanitizeSettings({
      ...DEFAULT_SETTINGS,
      default_initial_capital: Number.NaN,
    } as unknown);
    for (const value of Object.values(cleaned)) {
      if (typeof value === "number") {
        expect(Number.isFinite(value), `non-finite setting value: ${value}`).toBe(true);
      }
    }
  });
});

describe("loadSettings", () => {
  it("returns defaults when nothing is stored", () => {
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it("returns defaults when the stored value is malformed JSON", () => {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, "{not json");
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it("returns defaults when the stored value is valid JSON of the wrong shape", () => {
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(["nope"]));
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it("returns defaults when localStorage itself is unavailable", () => {
    stubUnavailableLocalStorage();
    expect(() => loadSettings()).not.toThrow();
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
  });

  it("round-trips a saved value", () => {
    const saved = saveSettings({ ...DEFAULT_SETTINGS, accent_color: "emerald", default_initial_capital: 12500, default_transaction_cost_bps: 0 });
    expect(loadSettings()).toEqual(saved);
    expect(loadSettings().accent_color).toBe("emerald");
    expect(loadSettings().default_transaction_cost_bps).toBe(0);
  });

  it("returns defaults when access to the storage property itself is denied", () => {
    Object.defineProperty(window, "localStorage", { configurable: true, get() { throw new Error("storage denied"); } });
    expect(loadSettings()).toEqual(DEFAULT_SETTINGS);
    expect(() => saveSettings(DEFAULT_SETTINGS)).not.toThrow();
    expect(() => resetSettings()).not.toThrow();
  });

  it("imports and reads defaults without a browser", async () => {
    vi.stubGlobal("window", undefined);
    vi.resetModules();
    const server = await import("@/lib/settings");
    expect(server.loadSettings()).toEqual(DEFAULT_SETTINGS);
    expect(server.resetSettings()).toEqual(DEFAULT_SETTINGS);
  });
});

describe("saveSettings / resetSettings", () => {
  it("does not throw when storage refuses writes", () => {
    stubUnavailableLocalStorage();
    expect(() => saveSettings({ ...DEFAULT_SETTINGS })).not.toThrow();
    expect(() => resetSettings()).not.toThrow();
  });

  it("clears the stored value on reset", () => {
    saveSettings({ ...DEFAULT_SETTINGS });
    expect(window.localStorage.getItem(SETTINGS_STORAGE_KEY)).not.toBeNull();
    resetSettings();
    expect(window.localStorage.getItem(SETTINGS_STORAGE_KEY)).toBeNull();
  });

  it("stores a sanitized value, never the raw input", () => {
    saveSettings({ ...DEFAULT_SETTINGS, accent_color: "bogus" } as never);
    const stored = JSON.parse(
      window.localStorage.getItem(SETTINGS_STORAGE_KEY) ?? "{}",
    );
    expect(stored.accent_color).toBe(DEFAULT_SETTINGS.accent_color);
  });
});
