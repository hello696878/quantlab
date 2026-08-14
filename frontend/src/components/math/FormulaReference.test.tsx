/**
 * Formula reference + SafeMath tests (Phase 63.0).
 *
 * These cover the shared math surface every lab embeds: that grouped formulas
 * render, that a malformed formula degrades instead of crashing the page, and
 * that "Copy LaTeX" copies the LaTeX SOURCE — and says so honestly when the
 * browser refuses clipboard access.
 */

import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FormulaReference from "@/components/math/FormulaReference";
import SafeMath from "@/components/math/SafeMath";
import { buildFormulaLatexText } from "@/components/math/formulaUtils";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import { renderWithUser, stubClipboard } from "@/test/testUtils";

const GROUPS: FormulaGroup[] = [
  {
    title: "Returns",
    description: "Close-to-close conventions.",
    formulas: [
      {
        label: "Simple return",
        latex: "r_t = \\frac{P_t}{P_{t-1}} - 1",
        note: "Close-to-close, no dividends.",
      },
      { label: "Log return", latex: "\\ln(P_t / P_{t-1})" },
    ],
  },
  {
    title: "Risk",
    formulas: [
      { label: "Volatility", latex: "\\sigma = \\sqrt{\\operatorname{Var}(r)}" },
    ],
  },
];

describe("SafeMath", () => {
  it("renders valid LaTeX through the local KaTeX renderer", () => {
    const { container } = renderWithUser(<SafeMath latex="x^2 + y^2" />);
    expect(container.querySelector(".ql-math")).not.toBeNull();
    expect(container.querySelector(".katex")).not.toBeNull();
  });

  it("does not crash on malformed LaTeX", () => {
    expect(() =>
      renderWithUser(<SafeMath latex="\\frac{unbalanced" />),
    ).not.toThrow();
  });

  it("falls back to readable raw LaTeX when the renderer throws", async () => {
    vi.resetModules();
    vi.doMock("katex", () => ({
      default: {
        renderToString: () => {
          throw new Error("katex exploded");
        },
      },
    }));
    const { default: Isolated } = await import("@/components/math/SafeMath");
    const { container } = renderWithUser(<Isolated latex="\\gamma_{fail}" />);
    const code = container.querySelector("code");
    expect(code, "the fallback must show the raw LaTeX source").not.toBeNull();
    expect(code).toHaveTextContent("\\gamma_{fail}");
    vi.doUnmock("katex");
    vi.resetModules();
  });
});

describe("buildFormulaLatexText", () => {
  it("emits LaTeX source only — never rendered HTML", () => {
    const text = buildFormulaLatexText(GROUPS, "Test formulas");
    expect(text).toContain("r_t = \\frac{P_t}{P_{t-1}} - 1");
    expect(text).not.toContain("<span");
    expect(text).not.toContain("katex");
  });

  it("includes every group heading and label", () => {
    const text = buildFormulaLatexText(GROUPS, "Test formulas");
    for (const group of GROUPS) {
      expect(text).toContain(group.title);
      for (const item of group.formulas) expect(text).toContain(item.label);
    }
  });
});

describe("FormulaReference", () => {
  it("renders the title, group headings, labels and notes", () => {
    renderWithUser(
      <FormulaReference title="Return formulas" subtitle="Reference" groups={GROUPS} />,
    );
    expect(screen.getByText("Return formulas")).toBeInTheDocument();
    expect(screen.getByText("Reference")).toBeInTheDocument();
    expect(screen.getByText("Returns")).toBeInTheDocument();
    expect(screen.getByText("Risk")).toBeInTheDocument();
    expect(screen.getByText("Simple return")).toBeInTheDocument();
    expect(screen.getByText("Close-to-close, no dividends.")).toBeInTheDocument();
  });

  it("copies the LaTeX source and confirms the copy", async () => {
    const { user } = renderWithUser(
      <FormulaReference title="Return formulas" groups={GROUPS} />,
    );
    // After renderWithUser: userEvent.setup() installs its own clipboard stub.
    const { writeText } = stubClipboard("ok");
    await user.click(screen.getByRole("button", { name: /Copy the LaTeX formula reference/i }));
    expect(writeText).toHaveBeenCalledTimes(1);
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain("r_t = \\frac{P_t}{P_{t-1}} - 1");
    expect(copied).not.toContain("<span");
    await waitFor(() => expect(screen.getByText(/Copied LaTeX formulas/i)).toBeInTheDocument());
  });

  it("shows the documented failure state when the clipboard rejects", async () => {
    const { user } = renderWithUser(
      <FormulaReference title="Return formulas" groups={GROUPS} />,
    );
    stubClipboard("reject");
    await user.click(screen.getByRole("button", { name: /Copy the LaTeX formula reference/i }));
    await waitFor(() =>
      expect(screen.getByText(/Could not copy formulas automatically/i)).toBeInTheDocument(),
    );
  });

  it("shows the failure state when the clipboard API is absent entirely", async () => {
    const { user } = renderWithUser(
      <FormulaReference title="Return formulas" groups={GROUPS} />,
    );
    stubClipboard("absent");
    await user.click(screen.getByRole("button", { name: /Copy the LaTeX formula reference/i }));
    await waitFor(() =>
      expect(screen.getByText(/Could not copy formulas automatically/i)).toBeInTheDocument(),
    );
  });

  it("hides the copy control when copying is disabled", () => {
    renderWithUser(
      <FormulaReference title="Return formulas" groups={GROUPS} copyable={false} />,
    );
    expect(screen.queryByRole("button", { name: /Copy the LaTeX formula reference/i })).toBeNull();
  });

  it("keeps long formulas inside their own scroll container", () => {
    const long: FormulaGroup[] = [
      {
        title: "Long",
        formulas: [
          {
            label: "Very long expression",
            latex: Array.from({ length: 40 }, (_, i) => `a_{${i}}`).join(" + "),
          },
        ],
      },
    ];
    const { container } = renderWithUser(
      <FormulaReference title="Long formulas" groups={long} />,
    );
    // `.ql-math` carries the horizontal-scroll rules in globals.css, so a wide
    // equation can never widen the page itself.
    expect(container.querySelector(".ql-math")).not.toBeNull();
  });

  it("collapses and expands without losing its accessible control", async () => {
    const { user } = renderWithUser(
      <FormulaReference title="Return formulas" groups={GROUPS} collapsible />,
    );
    // Collapsed content stays mounted behind `display: none`, so visibility —
    // not presence — is the honest assertion.
    expect(screen.getByText("Simple return")).not.toBeVisible();
    expect(screen.getByText(/formula groups hidden/i)).toBeVisible();
    const toggle = screen.getByRole("button", { name: /Show the formula reference/i });
    await user.click(toggle);
    expect(screen.getByText("Simple return")).toBeVisible();
  });
});
