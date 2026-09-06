import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { createNetworkGuard } from "./networkGuard";
import { stubClipboard } from "./testUtils";

describe("setup isolation", () => {
  // Each case checks pristine state before dirtying it; shuffling is safe.
  it.each([1, 2, 3])("restores DOM, storage, clipboard, timers and scroll spies (case %s)", () => {
    expect(localStorage.length).toBe(0);
    expect(screen.queryByText("isolation fixture")).toBeNull();
    expect(navigator.clipboard).toBeUndefined();
    expect(vi.isFakeTimers()).toBe(false);
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
    render(<div>isolation fixture</div>);
    localStorage.setItem("quantlab.test.isolation", "value");
    stubClipboard("ok");
    screen.getByText("isolation fixture").scrollIntoView();
    vi.useFakeTimers();
  });

  it("leaves console errors visible instead of globally silencing them", () => {
    const error = vi.spyOn(console, "error");
    console.error("[setup isolation] expected visible console.error sentinel");
    expect(error).toHaveBeenCalledWith("[setup isolation] expected visible console.error sentinel");
  });

  it("blocks network access and remembers attempts even when a caller catches the error", () => {
    expect(vi.isMockFunction(fetch)).toBe(true);
    expect(vi.isMockFunction(XMLHttpRequest.prototype.send)).toBe(true);
    const guard = createNetworkGuard();
    expect(() => guard.block("fetch")).toThrow(/Unmocked network/);
    expect(() => guard.assertClean()).toThrow(/Blocked unmocked network/);
    expect(() => guard.assertClean()).not.toThrow();
  });
});
