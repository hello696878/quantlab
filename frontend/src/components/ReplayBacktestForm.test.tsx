import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import BacktestForm from "./BacktestForm";
import type { BacktestRequest } from "@/lib/types";
import { executeSmaRequest, type ReplayRestore } from "@/lib/runReplay";

const fullRequest: BacktestRequest = {
  ticker: "BTC-USD", start_date: "2020-02-03", end_date: "2021-04-05", fast_window: 7, slow_window: 31,
  initial_capital: 234567, transaction_cost_bps: 10,
  cost_model: { type: "simple_bps", transaction_cost_bps: 37 }, position_mode: "long_short",
  position_sizing: { type: "volatility_target", target_volatility: .23, lookback_days: 17, max_exposure: .73 },
  risk_management: { type: "combined", stop_loss_pct: .07, take_profit_pct: .19, trailing_stop_pct: .04, max_holding_days: 13 },
  annualization_mode: "auto", benchmark: { mode: "custom_ticker", ticker: "QQQ" },
  robustness: { enabled: true, method: "block_bootstrap_returns", n_simulations: 213, block_size: 7, seed: 19 },
  sensitivity: { enabled: true, metric: "cagr", x_param: "fast_window", y_param: "slow_window", x_values: [3, 7], y_values: [21, 31], max_runs: 4 },
};

function ActualForm({ request, restored = null, onStrategyChange = vi.fn() }: {
  request: BacktestRequest; restored?: ReplayRestore | null; onStrategyChange?: () => void;
}) {
  const [params, setParams] = useState(request);
  const noop = vi.fn();
  return <BacktestForm strategy="sma_crossover" onStrategyChange={onStrategyChange} smaParams={params} onSmaParamsChange={setParams}
    rsiParams={{ ...params, rsi_window: 14, oversold_threshold: 30, exit_threshold: 50 }} onRsiParamsChange={noop}
    bbParams={{ ...params, bb_window: 20, num_std: 2, exit_band: "middle" }} onBbParamsChange={noop}
    momentumParams={{ ...params, momentum_window: 126, entry_threshold: 0, exit_threshold: 0 }} onMomentumParamsChange={noop}
    vbParams={{ ...params, lookback_window: 20, breakout_multiplier: 1, exit_window: 10 }} onVbParamsChange={noop}
    pairsParams={{ asset_y: "KO", asset_x: "PEP", start_date: params.start_date, end_date: params.end_date, initial_capital: 100000, transaction_cost_bps: 10, lookback_window: 60, entry_z_score: 2, exit_z_score: .5 }}
    onPairsParamsChange={noop} onSubmit={() => void executeSmaRequest(params, restored)} loading={false}
    localReplay={restored?.preflight.canonical_config.data_provider === "csv_upload"} />;
}

it.each([
  fullRequest,
  { ...fullRequest, cost_model: { type: "commission_slippage" as const, commission_bps: 2.5 } },
  { ...fullRequest, cost_model: { type: "conservative" as const }, position_sizing: { type: "fixed_fraction" as const, fraction: .41 }, benchmark: { mode: "none" as const } },
])("the actual SMA form emits every restored nondefault setting without a mount-time run", async (request) => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 200 })); vi.stubGlobal("fetch", fetch);
  render(<ActualForm request={request} />);
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Run Backtest" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  expect(fetch.mock.calls[0][0]).toBe("/api/backtest/sma-crossover");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(request);
});

it("shows absent recorded commission components as zero, including when one component is edited", async () => {
  const request = { ...fullRequest, cost_model: { type: "commission_slippage" as const, commission_bps: 2.5 } };
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 200 })); vi.stubGlobal("fetch", fetch);
  render(<ActualForm request={request} />);
  expect(screen.getAllByDisplayValue("0")).toHaveLength(2);
  fireEvent.change(screen.getByDisplayValue("2.5"), { target: { value: "3.5" } });
  fireEvent.click(screen.getByRole("button", { name: "Run Backtest" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  expect(JSON.parse(fetch.mock.calls[0][1].body).cost_model).toEqual({ type: "commission_slippage", commission_bps: 3.5, slippage_bps: 0, spread_bps: 0 });
});

it("keeps retained input local after edits or clicking the active strategy", async () => {
  const request = { ...fullRequest, benchmark: { mode: "none" as const } };
  const restored: ReplayRestore = {
    request, csvText: "Date,Close\n2020-02-03,100",
    preflight: {
      schema_version: "replay_preflight_v1", context_id: 19,
      config_hash_full: "a".repeat(64), canonical_config: { data_provider: "csv_upload" },
      input_hash: "b".repeat(64), environment_hash: null,
      result_hash: "c".repeat(64), execution_hash: "d".repeat(64),
      original_request: { ...request }, restore_request: request, restore_level: "recorded_settings",
      dataset: null, artifact: { run_id: 1, role: "input_csv", material_hash: "b".repeat(64) },
      data_availability: "retained_verified", integrity: "intact", ready_with_retained_data: true,
      environment_comparison: [], limitations: [],
    },
  };
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 200 })); vi.stubGlobal("fetch", fetch);
  const changed = vi.fn();
  render(<ActualForm request={request} restored={restored} onStrategyChange={changed} />);
  expect(screen.getByDisplayValue("BTC-USD")).toBeDisabled();
  expect(screen.getByDisplayValue("2020-02-03")).toBeDisabled();
  expect(screen.getByRole("button", { name: /RSI Mean Reversion/ })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /SMA Crossover/ }));
  expect(changed).not.toHaveBeenCalled();
  // A window edit must change only its setting, never detach the input binding.
  const fast = screen.getAllByRole("spinbutton").find((input) => input.getAttribute("max") === "30")!;
  fireEvent.change(fast, { target: { value: "9" } });
  expect(fetch).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Run Backtest" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  expect(fetch.mock.calls[0][0]).toBe("/api/run-replay/contexts/19/execute-local");
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ request: { ...request, fast_window: 9 }, csv_text: restored.csvText });
});

it("changing the sensitivity metric preserves the recorded custom grid and run cap", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { status: 200 })); vi.stubGlobal("fetch", fetch);
  render(<ActualForm request={fullRequest} />);
  fireEvent.click(screen.getByRole("button", { name: "Total Return" }));
  fireEvent.click(screen.getByRole("button", { name: "Run Backtest" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
  expect(JSON.parse(fetch.mock.calls[0][1].body).sensitivity).toEqual({ ...fullRequest.sensitivity, metric: "total_return" });
});

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
