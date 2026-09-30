import { expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { isMLLifecycleLink, useMLLifecycleLinkCleanup, writeMLLifecycleLink } from "./mlLifecycleLink";
import { readSwitcherViewIds } from "@/test/sourceScan";

it("maps the lifecycle identity to a real component and rejects unrelated links", () => {
  expect(readSwitcherViewIds()).toContain("mllifecycle");
  expect(isMLLifecycleLink("?view=strategyensemble")).toBe(false);
  expect(isMLLifecycleLink("?view=mllifecycle")).toBe(true);
});

it("replaces globe state while preserving unrelated query values and fragments", () => {
  history.replaceState(null, "", "/?view=globe&market=tw&tour=asia&presentation=1&x=1#note");
  writeMLLifecycleLink(true);
  expect(location.search).toBe("?view=mllifecycle&x=1");
  expect(location.hash).toBe("#note");
  const push = vi.spyOn(history, "pushState");
  writeMLLifecycleLink(true);
  expect(push).not.toHaveBeenCalled();
  writeMLLifecycleLink(false);
  expect(location.search).toBe("?x=1");
});

it("preserves the initial permalink and clears it when direct navigation leaves", () => {
  history.replaceState(null, "", "/?view=mllifecycle&x=1");
  const { rerender } = renderHook(({ view }) => useMLLifecycleLinkCleanup(view), { initialProps: { view: "home" } });
  expect(isMLLifecycleLink()).toBe(true);
  rerender({ view: "mllifecycle" });
  rerender({ view: "portfolio" });
  expect(location.search).toBe("?x=1");
});

it.each(["/?view=strategyensemble", "/?view=globe&market=tw", "/"])(
  "does not rewrite a destination already set by browser history (%s)", (destination) => {
    history.replaceState(null, "", "/?view=mllifecycle");
    const { rerender } = renderHook(({ view }) => useMLLifecycleLinkCleanup(view), { initialProps: { view: "mllifecycle" } });
    history.replaceState(null, "", destination);
    const push = vi.spyOn(history, "pushState");
    rerender({ view: "home" });
    expect(push).not.toHaveBeenCalled();
    expect(location.pathname + location.search).toBe(destination);
  });

it("is safe without browser globals", () => {
  vi.stubGlobal("window", undefined);
  expect(isMLLifecycleLink()).toBe(false);
  expect(() => writeMLLifecycleLink(true)).not.toThrow();
});
