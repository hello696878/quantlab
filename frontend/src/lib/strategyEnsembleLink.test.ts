import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { isStrategyEnsembleLink, useStrategyEnsembleLinkCleanup, writeStrategyEnsembleLink } from "./strategyEnsembleLink";
import { WORKSPACE_COMMANDS, WORKSPACE_BY_ID } from "./workspaceRegistry";
import { readSwitcherViewIds } from "@/test/sourceScan";

describe("strategy ensemble workspace", () => {
  it("is registered across navigation and the real component switcher", () => {
    expect(WORKSPACE_BY_ID.strategyensemble?.publicWorkspace).toBe(true);
    expect(WORKSPACE_COMMANDS.some((c) => c.view === "strategyensemble")).toBe(true);
    expect(readSwitcherViewIds()).toContain("strategyensemble");
  });
  it("only accepts its exact view id", () => {
    expect(isStrategyEnsembleLink("?view=strategyensemble")).toBe(true);
    expect(isStrategyEnsembleLink("?view=signalensemble")).toBe(false);
    expect(isStrategyEnsembleLink("?view=unknown")).toBe(false);
  });
  it("replaces globe state without losing unrelated query values", () => {
    history.replaceState(null, "", "/?view=globe&market=tw&tour=asia&x=1");
    writeStrategyEnsembleLink(true);
    expect(isStrategyEnsembleLink()).toBe(true);
    expect(location.search).toBe("?view=strategyensemble&x=1");
    const push = vi.spyOn(history, "pushState");
    writeStrategyEnsembleLink(true);
    expect(push).not.toHaveBeenCalled();
    writeStrategyEnsembleLink(false);
    expect(location.search).toBe("?x=1");
  });
  it("is safe without browser globals", () => {
    vi.stubGlobal("window", undefined);
    expect(isStrategyEnsembleLink()).toBe(false);
    expect(() => writeStrategyEnsembleLink(true)).not.toThrow();
  });
  it("preserves initial deep links but clears them when demo navigation leaves the lab", () => {
    history.replaceState(null, "", "/?view=strategyensemble&x=1");
    const { rerender } = renderHook(({ view }) => useStrategyEnsembleLinkCleanup(view), { initialProps: { view: "home" } });
    expect(isStrategyEnsembleLink()).toBe(true);
    rerender({ view: "strategyensemble" });
    expect(isStrategyEnsembleLink()).toBe(true);
    rerender({ view: "portfolio" });
    expect(location.search).toBe("?x=1");
  });
  it("does not rewrite a destination already set by browser history", () => {
    history.replaceState(null, "", "/?view=strategyensemble");
    const { rerender } = renderHook(({ view }) => useStrategyEnsembleLinkCleanup(view), { initialProps: { view: "strategyensemble" } });
    history.replaceState(null, "", "/?view=globe&market=tw");
    const push = vi.spyOn(history, "pushState");
    rerender({ view: "globe" });
    expect(push).not.toHaveBeenCalled();
    expect(location.search).toBe("?view=globe&market=tw");
  });
});
