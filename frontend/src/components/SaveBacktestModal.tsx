"use client";

import { useState } from "react";
import { classifyApiError, createSavedBacktest } from "@/lib/api";
import type { BacktestResponse, SavedBacktestCreate } from "@/lib/types";
import { notifyBackendOffline, toast } from "@/lib/toast";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildDefaultName(result: BacktestResponse): string {
  const ticker = result.ticker.toUpperCase();
  const strategyLabels: Record<string, string> = {
    sma_crossover: "SMA Crossover",
    rsi_mean_reversion: "RSI Mean Reversion",
    bollinger_band: "Bollinger Band",
    momentum: "Momentum",
    volatility_breakout: "Volatility Breakout",
    pairs: "Pairs Trading",
  };
  const label = strategyLabels[result.strategy] ?? result.strategy;
  return `${ticker} — ${label}`;
}

function buildParams(result: BacktestResponse): Record<string, unknown> {
  let params: Record<string, unknown> = {};
  if (result.strategy === "sma_crossover") {
    params = { fast_window: result.fast_window, slow_window: result.slow_window };
  }
  if (result.strategy === "rsi_mean_reversion") {
    params = {
      rsi_window: result.rsi_window,
      oversold_threshold: result.oversold_threshold,
      exit_threshold: result.exit_threshold,
    };
  }
  if (result.strategy === "bollinger_band") {
    params = {
      bb_window: result.bb_window,
      num_std: result.bb_num_std,
      exit_band: result.bb_exit_band,
    };
  }
  if (result.strategy === "momentum") {
    params = {
      momentum_window: result.momentum_window,
      entry_threshold: result.momentum_entry_threshold,
      exit_threshold: result.momentum_exit_threshold,
    };
  }
  if (result.strategy === "volatility_breakout") {
    params = {
      lookback_window: result.vb_lookback_window,
      breakout_multiplier: result.vb_breakout_multiplier,
      exit_window: result.vb_exit_window,
    };
  }
  if (result.strategy === "pairs") {
    params = {
      asset_y: result.pairs_asset_y,
      asset_x: result.pairs_asset_x,
      lookback_window: result.pairs_lookback_window,
      entry_z_score: result.pairs_entry_z_score,
      exit_z_score: result.pairs_exit_z_score,
    };
  }

  if (result.cost_model) {
    params.cost_model = result.cost_model;
  }
  if (typeof result.effective_cost_bps === "number") {
    params.effective_cost_bps = result.effective_cost_bps;
  }
  if (typeof result.total_transaction_cost === "number") {
    params.total_transaction_cost = result.total_transaction_cost;
  }
  if (typeof result.cost_drag_return === "number") {
    params.cost_drag_return = result.cost_drag_return;
  }
  if (result.position_sizing) {
    params.position_sizing = result.position_sizing;
  }
  if (typeof result.average_exposure === "number") {
    params.average_exposure = result.average_exposure;
  }
  if (result.risk_management) {
    params.risk_management = result.risk_management;
  }
  if (result.risk_diagnostics) {
    params.risk_diagnostics = result.risk_diagnostics;
  }
  if (result.periods_per_year) {
    params.annualization_mode = result.annualization_mode;
    params.annualization_mode_used = result.annualization_mode_used;
    params.periods_per_year = result.periods_per_year;
    params.annualization_warning = result.annualization_warning ?? null;
  }
  if (result.data_provider) {
    params.data_provider = result.data_provider;
  }
  if (result.data_quality) {
    params.data_quality = result.data_quality;
  }
  if (result.benchmark_analytics) {
    // Persist config + metrics; drop the bulky curve / nested diagnostics.
    const { equity_curve: _curve, data_quality: _dq, ...trimmed } =
      result.benchmark_analytics;
    params.benchmark_analytics = trimmed;
  }
  return params;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface SaveBacktestModalProps {
  result: BacktestResponse;
  onSaved: (id: number) => void;
  onCancel: () => void;
}

export default function SaveBacktestModal({
  result,
  onSaved,
  onCancel,
}: SaveBacktestModalProps) {
  const [name, setName] = useState(buildDefaultName(result));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nameOk = name.trim().length > 0;

  async function handleSave() {
    if (!nameOk || saving) return;
    setSaving(true);
    setError(null);

    const payload: SavedBacktestCreate = {
      name: name.trim(),
      ticker: result.ticker,
      strategy: result.strategy,
      start_date: result.start_date,
      end_date: result.end_date,
      initial_capital: result.initial_capital,
      transaction_cost_bps: result.transaction_cost_bps,
      params: {
        ...buildParams(result),
        // Preserve the direction mode (long_only / short_only / long_short).
        // Older saved records simply omit it and load as long_only.
        ...(result.position_mode ? { position_mode: result.position_mode } : {}),
      },
      metrics: result.strategy_metrics as unknown as Record<string, unknown>,
      equity_curve: result.equity_curve,
      trades: result.trades,
      notes: notes.trim(),
    };

    try {
      const saved = await createSavedBacktest(payload);
      toast.success("Backtest saved", `"${saved.name}" stored locally.`);
      onSaved(saved.id);
    } catch (err) {
      const cls = classifyApiError(err);
      if (cls.backendUnavailable) notifyBackendOffline();
      else toast.error("Save failed", cls.message);
      setError(cls.message);
      setSaving(false);
    }
  }

  return (
    <div className="card p-5 border-2 border-blue-200 bg-blue-50/40">
      <p className="text-sm font-semibold text-slate-800 mb-3">
        Save this backtest
      </p>

      <div className="space-y-3">
        {/* Name */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">
            Name <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. SPY — SMA Crossover (long run)"
            className={
              "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none " +
              "focus:ring-2 focus:ring-blue-400 " +
              (nameOk ? "border-slate-200 bg-white" : "border-red-300 bg-red-50")
            }
          />
          {!nameOk && (
            <p className="text-xs text-red-600 mt-1">Name cannot be empty.</p>
          )}
        </div>

        {/* Notes */}
        <div>
          <label className="block text-xs font-medium text-slate-600 mb-1">
            Notes{" "}
            <span className="text-slate-400 font-normal">(optional)</span>
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            placeholder="Observations, hypotheses, follow-up ideas…"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm
                       focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none"
          />
        </div>

        {/* Error */}
        {error && (
          <p className="text-xs text-red-600 bg-red-50 rounded px-2 py-1">
            {error}
          </p>
        )}

        {/* Buttons */}
        <div className="flex gap-2 justify-end pt-1">
          <button
            type="button"
            onClick={onCancel}
            disabled={saving}
            className="px-4 py-1.5 rounded-lg text-sm font-medium text-slate-600
                       border border-slate-200 hover:bg-slate-100 transition-colors
                       disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={!nameOk || saving}
            className="px-4 py-1.5 rounded-lg text-sm font-semibold text-white
                       bg-blue-600 hover:bg-blue-700 transition-colors
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving…" : "Save backtest"}
          </button>
        </div>
      </div>
    </div>
  );
}
