"use client";

/**
 * Market Microstructure & Execution Lab v1 (Phase 25.0).
 *
 * Deterministic static-sample microstructure / execution analytics: limit
 * order-book summary (spread, depth ladder, imbalance, microprice), trade-tape
 * analytics (VWAP / TWAP / trade imbalance), execution analytics (implementation
 * shortfall, slippage, participation, square-root market-impact approximation), a
 * hypothetical execution-schedule comparison, and liquidity stress scenarios.
 *
 * All numbers come from the backend static-sample API — no live order books or
 * trades, no broker / exchange integration, educational only, not investment,
 * trading, or order-routing advice, and not a production execution system.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeMicrostructure,
  bps,
  compact,
  fetchMicrostructureSample,
  num,
  signedBps,
  type MarketMicrostructureAnalysisRequest,
  type MarketMicrostructureAnalysisResponse,
  type MicrostructureSampleResponse,
} from "@/lib/microstructure";

const REQUEST_FIELDS = [
  { key: "quantity", label: "Parent qty", step: "1", scope: "order" as const },
  { key: "arrival_price", label: "Arrival price", step: "0.01", scope: "order" as const },
  { key: "average_daily_volume", label: "ADV", step: "1000", scope: "root" as const },
  { key: "volatility_bps", label: "Volatility (bps)", step: "10", scope: "root" as const },
  { key: "impact_coefficient", label: "Impact coeff.", step: "0.05", scope: "root" as const },
];

const MICROSTRUCTURE_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Order book",
    formulas: [
      { label: "Mid price", latex: "m = \\frac{b_{\\mathrm{best}} + a_{\\mathrm{best}}}{2}" },
      { label: "Spread", latex: "s = a_{\\mathrm{best}} - b_{\\mathrm{best}}" },
      { label: "Spread (bps)", latex: "s_{\\mathrm{bps}} = \\frac{a_{\\mathrm{best}} - b_{\\mathrm{best}}}{m} \\times 10{,}000" },
      { label: "Top-of-book imbalance", latex: "I_1 = \\frac{Q_b^{(1)} - Q_a^{(1)}}{Q_b^{(1)} + Q_a^{(1)}}" },
      { label: "Depth imbalance", latex: "I_K = \\frac{\\sum_{i=1}^{K} Q_b^{(i)} - \\sum_{i=1}^{K} Q_a^{(i)}}{\\sum_{i=1}^{K} Q_b^{(i)} + \\sum_{i=1}^{K} Q_a^{(i)}}" },
      { label: "Microprice", latex: "p_{\\mathrm{micro}} = \\frac{a_{\\mathrm{best}} Q_b^{(1)} + b_{\\mathrm{best}} Q_a^{(1)}}{Q_b^{(1)} + Q_a^{(1)}}" },
    ],
  },
  {
    title: "Trade tape",
    formulas: [
      { label: "VWAP", latex: "\\mathrm{VWAP} = \\frac{\\sum_i p_i q_i}{\\sum_i q_i}" },
      { label: "TWAP", latex: "\\mathrm{TWAP} = \\frac{1}{N}\\sum_i p_i" },
      { label: "Signed volume", latex: "\\tilde{q}_i = \\begin{cases} q_i, & \\text{buyer initiated} \\\\ -q_i, & \\text{seller initiated} \\end{cases}" },
      { label: "Trade imbalance", latex: "I_{\\mathrm{trade}} = \\frac{\\sum_i \\tilde{q}_i}{\\sum_i q_i}" },
    ],
  },
  {
    title: "Execution",
    formulas: [
      { label: "Average execution price", latex: "\\bar{p}_{\\mathrm{exec}} = \\frac{\\sum_i p_i q_i}{\\sum_i q_i}" },
      { label: "Fill ratio", latex: "\\mathrm{FillRatio} = \\frac{\\sum_i q_i}{Q}" },
      { label: "Implementation shortfall (buy)", latex: "\\mathrm{IS}_{\\mathrm{buy}} = \\frac{\\bar{p}_{\\mathrm{exec}} - p_{\\mathrm{arrival}}}{p_{\\mathrm{arrival}}}" },
      { label: "Implementation shortfall (sell)", latex: "\\mathrm{IS}_{\\mathrm{sell}} = \\frac{p_{\\mathrm{arrival}} - \\bar{p}_{\\mathrm{exec}}}{p_{\\mathrm{arrival}}}" },
      { label: "Participation rate", latex: "\\mathrm{POV} = \\frac{Q_{\\mathrm{executed}}}{V_{\\mathrm{market}}}" },
      { label: "Square-root market impact", latex: "\\mathrm{Impact}_{\\mathrm{bps}} = \\lambda \\sqrt{\\frac{Q}{\\mathrm{ADV}}}\\, \\sigma_{\\mathrm{bps}}" },
    ],
  },
  {
    title: "TCA / cost attribution",
    formulas: [
      { label: "Total execution cost", latex: "C_{\\mathrm{total}} = C_{\\mathrm{spread}} + C_{\\mathrm{impact}} + C_{\\mathrm{timing}} + C_{\\mathrm{fees}} + C_{\\mathrm{residual}}" },
      { label: "Spread cost", latex: "C_{\\mathrm{spread}} = \\tfrac{1}{2}\\, s_{\\mathrm{bps}}" },
      { label: "Timing cost (buy)", latex: "C_{\\mathrm{timing,buy}} = \\frac{p_{\\mathrm{benchmark}} - p_{\\mathrm{arrival}}}{p_{\\mathrm{arrival}}} \\times 10{,}000" },
      { label: "Timing cost (sell)", latex: "C_{\\mathrm{timing,sell}} = \\frac{p_{\\mathrm{arrival}} - p_{\\mathrm{benchmark}}}{p_{\\mathrm{arrival}}} \\times 10{,}000" },
      { label: "Fees", latex: "C_{\\mathrm{fees}} = \\frac{\\mathrm{fees}}{\\mathrm{notional}} \\times 10{,}000" },
    ],
  },
];

function imbColor(v: number): string {
  return v > 0.02 ? "var(--pos)" : v < -0.02 ? "var(--neg)" : "var(--text-hi)";
}

function costColor(v: number): string {
  return v > 0 ? "var(--neg)" : v < 0 ? "var(--pos)" : "var(--text-mut)";
}

export default function MicrostructureLabPanel() {
  const [sample, setSample] = useState<MicrostructureSampleResponse | null>(null);
  const [selected, setSelected] = useState(0);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<MarketMicrostructureAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFrom(req: MarketMicrostructureAnalysisRequest): Record<string, string> {
    const out: Record<string, string> = {};
    REQUEST_FIELDS.forEach((f) => {
      const src = f.scope === "order"
        ? (req.execution_order as unknown as Record<string, number>)
        : (req as unknown as Record<string, number>);
      out[f.key] = String(src[f.key]);
    });
    return out;
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchMicrostructureSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSelected(0);
        setFieldStr(fieldsFrom(s.instruments[0]));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  // Reset editable fields when the selected instrument changes.
  const base = sample?.instruments[selected] ?? null;
  function selectInstrument(idx: number) {
    if (!sample) return;
    setSelected(idx);
    setFieldStr(fieldsFrom(sample.instruments[idx]));
  }

  const request = useMemo<MarketMicrostructureAnalysisRequest | null>(() => {
    if (!base) return null;
    const orderOverrides: Record<string, number> = {};
    const rootOverrides: Record<string, number> = {};
    REQUEST_FIELDS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      const fallback = f.scope === "order"
        ? (base.execution_order as unknown as Record<string, number>)[f.key]
        : (base as unknown as Record<string, number>)[f.key];
      const val = Number.isFinite(v) && v > 0 ? v : fallback;
      if (f.scope === "order") orderOverrides[f.key] = val;
      else rootOverrides[f.key] = val;
    });
    return {
      ...base,
      ...rootOverrides,
      execution_order: { ...base.execution_order, ...orderOverrides },
    } as MarketMicrostructureAnalysisRequest;
  }, [base, fieldStr]);

  const reqKey = request
    ? JSON.stringify([request.order_book.symbol, request.execution_order, request.volatility_bps, request.impact_coefficient, request.average_daily_volume])
    : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeMicrostructure(request, ctrl.signal)
        .then((r) => {
          setResult(r);
          setAnalyzeError(null);
        })
        .catch((e: unknown) => {
          if (!ctrl.signal.aborted) setAnalyzeError(e instanceof Error ? e.message : "Analysis failed.");
        });
    }, 250);
    return () => {
      window.clearTimeout(timer);
      ctrl.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reqKey]);

  const r = result;

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Market Microstructure &amp; Execution Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const ob = r?.order_book_summary;
  const ex = r?.execution_summary;
  const tape = r?.trade_tape_summary;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Market Microstructure &amp; Execution Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Explore a sample limit order book — spread, depth ladder, order-book imbalance and
              microprice — plus trade-tape VWAP / TWAP, execution implementation shortfall,
              slippage, participation and a square-root market-impact approximation, a schedule
              comparison, and liquidity stress scenarios. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Market microstructure and execution analytics are educational and not investment, trading, order-routing, legal, tax, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Instrument selector + execution assumptions ──────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Instrument &amp; execution assumptions</p>
          {ex && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r?.instrument_summary.symbol} · {ex.side.toUpperCase()} parent</span>}
        </div>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {sample?.instruments.map((inst, i) => (
            <button key={inst.order_book.symbol} type="button" onClick={() => selectInstrument(i)} aria-pressed={selected === i}
              className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
              style={{
                background: selected === i ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selected === i ? "var(--accent-line)" : "var(--line)"}`,
                color: selected === i ? "var(--accent-text)" : "var(--text-hi)",
              }}>{inst.order_book.symbol.replace("_SAMPLE", "")}</button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
          {REQUEST_FIELDS.map((f) => (
            <label key={f.key} className="block">
              <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{f.label}</span>
              <input
                type="number"
                step={f.step}
                inputMode="decimal"
                aria-label={f.label}
                value={fieldStr[f.key] ?? ""}
                onChange={(e) => setFieldStr((s) => ({ ...s, [f.key]: e.target.value }))}
                className="ql-input mt-1 w-full px-2 py-1 text-sm"
              />
            </label>
          ))}
        </div>
      </div>

      {/* ── Key metrics ──────────────────────────────────────────────────── */}
      {r && ob && ex && (
        <div className="card p-4">
          <p className="section-title mb-2">Key metrics</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            <MetricCard label="Mid price" value={num(ob.mid_price, 2)} tone="accent" />
            <MetricCard label="Spread" value={bps(ob.spread_bps)} />
            <MetricCard label="Microprice Δ" value={signedBps(ob.microprice_vs_mid_bps)} tone={ob.microprice_vs_mid_bps >= 0 ? "positive" : "warn"} />
            <MetricCard label="Top imbalance" value={num(ob.top_of_book_imbalance, 3)} />
            <MetricCard label="VWAP" value={tape ? num(tape.vwap, 2) : "—"} />
            <MetricCard label="Impl. shortfall" value={signedBps(ex.shortfall_bps)} tone={ex.shortfall_bps > 0 ? "danger" : "positive"} />
            <MetricCard label="Participation" value={`${(ex.participation_rate * 100).toFixed(1)}%`} />
            <MetricCard label="Market impact" value={bps(ex.market_impact_bps)} tone="warn" />
          </div>
        </div>
      )}

      {/* ── Order book ladder + imbalance/microprice ─────────────────────── */}
      {r && ob && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4 xl:col-span-2">
            <p className="section-title mb-2">Order book depth ladder</p>
            <div className="overflow-x-auto">
              <table className="mono w-full text-[11px]">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-1.5 py-1 text-right">Cum bid</th>
                    <th className="px-1.5 py-1 text-right">Bid size</th>
                    <th className="px-1.5 py-1 text-right">Bid</th>
                    <th className="px-1.5 py-1 text-center">Lvl</th>
                    <th className="px-1.5 py-1 text-left">Ask</th>
                    <th className="px-1.5 py-1 text-left">Ask size</th>
                    <th className="px-1.5 py-1 text-left">Cum ask</th>
                  </tr>
                </thead>
                <tbody>
                  {r.depth_table.map((d) => (
                    <tr key={d.level} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-faint)" }}>{compact(d.cumulative_bid_size)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{compact(d.bid_size)}</td>
                      <td className="px-1.5 py-1 text-right font-semibold" style={{ color: "var(--pos)" }}>{num(d.bid_price, 2)}</td>
                      <td className="px-1.5 py-1 text-center" style={{ color: "var(--text-faint)" }}>{d.level}</td>
                      <td className="px-1.5 py-1 text-left font-semibold" style={{ color: "var(--neg)" }}>{num(d.ask_price, 2)}</td>
                      <td className="px-1.5 py-1 text-left" style={{ color: "var(--text-mut)" }}>{compact(d.ask_size)}</td>
                      <td className="px-1.5 py-1 text-left" style={{ color: "var(--text-faint)" }}>{compact(d.cumulative_ask_size)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Best bid {num(ob.best_bid, 2)} · best ask {num(ob.best_ask, 2)} · spread {num(ob.spread, 4)} ({bps(ob.spread_bps)}).
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Imbalance &amp; microprice</p>
            <div className="grid grid-cols-2 gap-2">
              <MetricCard label="Top-of-book imb." value={num(ob.top_of_book_imbalance, 3)} />
              <MetricCard label="Depth imb. (5)" value={num(ob.depth_imbalance_5, 3)} />
              <MetricCard label="Microprice" value={num(ob.microprice, 2)} tone="accent" />
              <MetricCard label="vs mid" value={signedBps(ob.microprice_vs_mid_bps)} tone={ob.microprice_vs_mid_bps >= 0 ? "positive" : "warn"} />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: imbColor(ob.depth_imbalance_5) }}>
              {ob.depth_imbalance_5 > 0.02
                ? "Bid-heavy book — more size resting on the buy side; microprice leans above mid."
                : ob.depth_imbalance_5 < -0.02
                  ? "Ask-heavy book — more size resting on the sell side; microprice leans below mid."
                  : "Roughly balanced book — microprice sits near the mid."}
            </p>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              microprice = (ask·bidSize + bid·askSize) / (bidSize + askSize).
            </p>
          </div>
        </div>
      )}

      {/* ── Trade tape + execution summary ───────────────────────────────── */}
      {r && tape && ex && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Trade tape summary</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Trades" value={String(tape.trade_count)} />
              <MetricCard label="Volume" value={compact(tape.total_volume)} />
              <MetricCard label="VWAP" value={num(tape.vwap, 2)} tone="accent" />
              <MetricCard label="TWAP" value={num(tape.twap, 2)} />
              <MetricCard label="Trade imb." value={num(tape.trade_imbalance, 3)} tone={tape.trade_imbalance >= 0 ? "positive" : "warn"} />
              <MetricCard label="Buy / sell" value={`${compact(tape.buy_volume)} / ${compact(tape.sell_volume)}`} />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              VWAP = Σ(price·size)/Σsize · TWAP = mean(price) · imbalance = signed volume / total volume.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Execution summary ({ex.side})</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Avg exec px" value={num(ex.average_execution_price, 2)} tone="accent" />
              <MetricCard label="Fill ratio" value={`${(ex.fill_ratio * 100).toFixed(1)}%`} />
              <MetricCard label="Filled qty" value={compact(ex.filled_quantity)} />
              <MetricCard label="Impl. shortfall" value={signedBps(ex.shortfall_bps)} tone={ex.shortfall_bps > 0 ? "danger" : "positive"} />
              <MetricCard label="Slippage" value={signedBps(ex.slippage_bps)} tone={ex.slippage_bps > 0 ? "danger" : "positive"} />
              <MetricCard label="Market impact" value={bps(ex.market_impact_bps)} tone="warn" />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Positive shortfall / slippage is an execution cost vs arrival / benchmark; impact uses a
              square-root model (impact = coeff · √(qty/ADV) · vol_bps).
            </p>
          </div>
        </div>
      )}

      {/* ── Execution schedule comparison ────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Execution schedule comparison (hypothetical)</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Schedule</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Children</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Exp. avg px</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Spread cost</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Impact</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Shortfall</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Participation</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Completion</th>
                </tr>
              </thead>
              <tbody>
                {r.schedule_comparison.map((s) => (
                  <tr key={s.schedule_name} style={{ borderTop: "1px solid var(--line)" }} title={s.notes.join(" ")}>
                    <td className="px-2 py-1.5 font-semibold" style={{ color: "var(--text-hi)" }}>{s.schedule_name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{s.child_orders}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{num(s.expected_avg_price, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{bps(s.expected_spread_cost_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{bps(s.expected_impact_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: costColor(s.expected_shortfall_bps) }}>{bps(s.expected_shortfall_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{(s.participation_rate * 100).toFixed(1)}%</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{(s.completion_rate * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hypothetical educational schedules on deterministic sample data — no schedule is
            recommended, and nothing here is order-routing advice.
          </p>
        </div>
      )}

      {/* ── Liquidity stress scenarios ───────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Liquidity stress scenarios</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Spread</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Depth</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Depth imb.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Microprice</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Immediate</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">TWAP</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">VWAP</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">POV</th>
                </tr>
              </thead>
              <tbody>
                {r.liquidity_scenarios.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{bps(s.spread_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{compact(s.total_depth)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: imbColor(s.depth_imbalance) }}>{num(s.depth_imbalance, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{num(s.microprice, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--neg)" }}>{bps(s.immediate_shortfall_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{bps(s.twap_shortfall_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{bps(s.vwap_shortfall_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{bps(s.pov_shortfall_bps)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Stressed spread / depth / volatility / volume scenarios — deterministic illustrative
            examples, not forecasts or trading advice.
          </p>
        </div>
      )}

      {/* ── TCA / Execution Cost Attribution ─────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">TCA / Execution Cost Attribution</p>
            <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>
              total {signedBps(r.tca.total_cost_bps)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            <MetricCard label="Arrival shortfall" value={signedBps(r.tca.benchmark_arrival_bps)} tone={r.tca.benchmark_arrival_bps > 0 ? "danger" : "positive"} />
            <MetricCard label="VWAP shortfall" value={signedBps(r.tca.benchmark_vwap_bps)} tone={r.tca.benchmark_vwap_bps > 0 ? "danger" : "positive"} />
            <MetricCard label="TWAP shortfall" value={signedBps(r.tca.benchmark_twap_bps)} tone={r.tca.benchmark_twap_bps > 0 ? "danger" : "positive"} />
            <MetricCard label="Spread cost" value={bps(r.tca.spread_cost_bps)} />
            <MetricCard label="Impact cost" value={bps(r.tca.impact_cost_bps)} tone="warn" />
            <MetricCard label="Timing cost" value={signedBps(r.tca.timing_cost_bps)} />
            <MetricCard label="Fees" value={bps(r.tca.fees_bps)} />
            <MetricCard label="Total cost" value={signedBps(r.tca.total_cost_bps)} tone="accent" />
          </div>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Component</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Cost</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Share</th>
                </tr>
              </thead>
              <tbody>
                {r.tca.attribution_rows.map((row) => (
                  <tr key={row.component} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row.component}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: costColor(row.cost_bps) }}>{signedBps(row.cost_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{(row.share * 100).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Deterministic educational TCA attribution. Not execution, routing, or trading advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={MICROSTRUCTURE_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — not a live order book or trade feed.</li>
          <li>The market-impact and schedule models are simplified educational approximations, not a production execution / cost model.</li>
          <li>Schedule comparison and stress scenarios are hypothetical — no schedule is recommended.</li>
          <li>Educational only — not investment, trading, order-routing, legal, tax, or risk-management advice.</li>
        </ul>
        {r?.notes && (
          <ul className="mt-3 space-y-1 text-[11px]" style={{ color: "var(--text-faint)" }}>
            {r.notes.map((n) => <li key={n}>• {n}</li>)}
          </ul>
        )}
      </div>
    </div>
  );
}
