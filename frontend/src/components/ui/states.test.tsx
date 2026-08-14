/**
 * Shared state-primitive tests (Phase 63.0).
 *
 * Every workspace routes its loading, empty, error and offline paths through
 * these four components, so a regression here is a regression everywhere. The
 * assertions are semantic (roles, accessible names, callbacks) rather than
 * class-name or snapshot based.
 */

import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import OfflineState from "@/components/ui/OfflineState";
import { SkeletonTable } from "@/components/ui/LoadingSkeleton";
import { renderWithUser } from "@/test/testUtils";

describe("EmptyState", () => {
  it("renders its title and description", () => {
    renderWithUser(
      <EmptyState title="No runs yet" description="Load the deterministic demo." />,
    );
    expect(screen.getByText("No runs yet")).toBeInTheDocument();
    expect(screen.getByText("Load the deterministic demo.")).toBeInTheDocument();
  });

  it("renders actions as accessible buttons and reports clicks", async () => {
    const onClick = vi.fn();
    const { user } = renderWithUser(
      <EmptyState
        title="No runs yet"
        description="Load the demo."
        actions={[{ label: "Load demo runs", onClick }]}
      />,
    );
    const button = screen.getByRole("button", { name: "Load demo runs" });
    await user.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("renders without actions", () => {
    renderWithUser(<EmptyState title="Nothing here" description="Yet." />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("ErrorState", () => {
  it("exposes the failure as an alert with its message", () => {
    renderWithUser(<ErrorState title="Couldn’t load" message="HTTP 500" />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Couldn’t load");
    expect(alert).toHaveTextContent("HTTP 500");
  });

  it("offers a retry control that reports the retry", async () => {
    const onRetry = vi.fn();
    const { user } = renderWithUser(
      <ErrorState title="Couldn’t load" message="HTTP 500" onRetry={onRetry} />,
    );
    await user.click(screen.getByRole("button", { name: /Retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("does not render a retry control when no handler is supplied", () => {
    renderWithUser(<ErrorState title="Couldn’t load" message="HTTP 500" />);
    expect(screen.queryByRole("button", { name: /Retry/i })).toBeNull();
  });
});

describe("OfflineState", () => {
  it("announces the offline condition as a live status region", () => {
    renderWithUser(<OfflineState />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("offers a retry control that reports the retry", async () => {
    const onRetry = vi.fn();
    const { user } = renderWithUser(<OfflineState onRetry={onRetry} />);
    await user.click(screen.getByRole("button", { name: /Retry/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("SkeletonTable", () => {
  it("announces loading with its caption as the accessible name", () => {
    renderWithUser(<SkeletonTable rows={3} cols={4} caption="Loading runs…" />);
    expect(screen.getByRole("status", { name: "Loading runs…" })).toBeInTheDocument();
  });

  it("renders no NaN or Infinity placeholder text", () => {
    const { container } = renderWithUser(
      <SkeletonTable rows={2} cols={2} caption="Loading…" />,
    );
    expect(container.textContent ?? "").toBeFiniteNumericText();
  });
});
