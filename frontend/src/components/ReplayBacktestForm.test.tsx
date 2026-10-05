import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import BacktestForm from "./BacktestForm";
import type { BacktestRequest } from "@/lib/types";

it("the real destination form preserves restored values, missing risk rules and explicit Run", () => {
  const params: BacktestRequest = { ticker: "REPLAY-DEMO", start_date: "2020-01-01", end_date: "2020-06-28",
    fast_window: 5, slow_window: 20, initial_capital: 100000, transaction_cost_bps: 10,
    cost_model: { type: "simple_bps", transaction_cost_bps: 10 }, position_mode: "long_only",
    risk_management: { type: "combined", stop_loss_pct: .07 }, annualization_mode: "trading_days_252" };
  const onChange = vi.fn(), run = vi.fn();
  const noop = vi.fn();
  render(<BacktestForm strategy="sma_crossover" onStrategyChange={noop} smaParams={params} onSmaParamsChange={onChange}
    rsiParams={{ ...params, rsi_window: 14, oversold_threshold: 30, exit_threshold: 50 }} onRsiParamsChange={noop}
    bbParams={{ ...params, bb_window: 20, num_std: 2, exit_band: "middle" }} onBbParamsChange={noop}
    momentumParams={{ ...params, momentum_window: 126, entry_threshold: 0, exit_threshold: 0 }} onMomentumParamsChange={noop}
    vbParams={{ ...params, lookback_window: 20, breakout_multiplier: 1, exit_window: 10 }} onVbParamsChange={noop}
    pairsParams={{ asset_y: "KO", asset_x: "PEP", start_date: params.start_date, end_date: params.end_date, initial_capital: 100000, transaction_cost_bps: 10, lookback_window: 60, entry_z_score: 2, exit_z_score: .5 }}
    onPairsParamsChange={noop} onSubmit={run} loading={false} />);
  expect(screen.getByDisplayValue("REPLAY-DEMO")).toBeVisible();
  expect(screen.getByDisplayValue("5")).toBeVisible();
  expect(screen.getAllByDisplayValue("").length).toBeGreaterThanOrEqual(3);
  expect(screen.queryByDisplayValue("0.2")).toBeNull();
  expect(run).not.toHaveBeenCalled();
  expect(onChange).not.toHaveBeenCalled();
  fireEvent.change(screen.getByDisplayValue("5"), { target: { value: "" } });
  expect(screen.queryByDisplayValue("5")).toBeNull();
  expect(run).not.toHaveBeenCalled();
  fireEvent.change(screen.getAllByRole("spinbutton").find((input) => input.getAttribute("min") === "2")!, { target: { value: "8" } });
  expect(onChange).toHaveBeenCalledWith({ ...params, fast_window: 8 });
});
