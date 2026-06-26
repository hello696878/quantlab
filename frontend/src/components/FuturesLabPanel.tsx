"use client";

/**
 * Futures & Commodities Lab v1 (Phase 23.0).
 *
 * Deterministic static-sample futures / commodities analytics: cost-of-carry
 * pricing, implied convenience yield, futures-curve shape (contango /
 * backwardation / mixed), roll yield, calendar spreads, contract notional /
 * margin / leverage P&L, and commodity scenario stress.
 *
 * All numbers come from the backend static-sample API — no live futures or
 * commodity data, educational only, not investment / trading advice.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeFutures,
  fetchFuturesSample,
  money,
  num,
  pct,
  type FuturesAnalysisRequest,
  type FuturesAnalysisResponse,
  type FuturesContractInput,
} from "@/lib/futures";

const FUTURES_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Pricing & curve",
    formulas: [
      { label: "Cost of carry", latex: "F = S\\, e^{(r + u - y)\\,T}", note: "Forward price from spot, financing r, storage u, convenience yield y." },
      { label: "Implied convenience yield", latex: "y = r + u - \\frac{\\ln(F/S)}{T}" },
      { label: "Basis", latex: "\\mathrm{Basis} = F - S" },
      { label: "Annualised basis", latex: "\\mathrm{Basis}_{\\mathrm{ann}} = \\frac{F/S - 1}{T}" },
      { label: "Roll yield", latex: "\\mathrm{RollYield} = \\frac{F_{\\mathrm{near}} - F_{\\mathrm{next}}}{F_{\\mathrm{near}}}" },
      { label: "Calendar spread", latex: "\\mathrm{CalSpread} = F_{\\mathrm{deferred}} - F_{\\mathrm{near}}" },
    ],
  },
  {
    title: "Contract P&L & margin",
    formulas: [
      { label: "Long P&L", latex: "\\mathrm{PnL}_{\\mathrm{long}} = (p_{\\mathrm{exit}} - p_{\\mathrm{entry}})\\, \\kappa\\, n", note: "κ = contract multiplier, n = contracts." },
      { label: "Short P&L", latex: "\\mathrm{PnL}_{\\mathrm{short}} = (p_{\\mathrm{entry}} - p_{\\mathrm{exit}})\\, \\kappa\\, n" },
      { label: "Notional & margin", latex: "\\mathrm{Margin} = \\mathrm{Notional} \\cdot m_{\\mathrm{rate}}" },
      { label: "Return on margin", latex: "\\mathrm{ROM} = \\frac{\\mathrm{PnL}}{\\mathrm{Margin}_{\\mathrm{initial}}}" },
    ],
  },
];

interface NumField {
  key: string;
  label: string;
  step: string;
}

const CONTRACT_FIELDS: NumField[] = [
  { key: "spot_price", label: "Spot price", step: "0.5" },
  { key: "risk_free_rate", label: "Risk-free rate", step: "0.0025" },
  { key: "storage_cost_rate", label: "Storage cost", step: "0.0025" },
  { key: "convenience_yield", label: "Convenience yield", step: "0.0025" },
  { key: "contract_multiplier", label: "Multiplier", step: "100" },
  { key: "initial_margin_rate", label: "Initial margin", step: "0.01" },
  { key: "maintenance_margin_rate", label: "Maint. margin", step: "0.01" },
];

function pnlColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

function shapeTone(shape: string): string {
  return shape === "contango" ? "var(--warn)" : shape === "backwardation" ? "var(--pos)" : "var(--text-mut)";
}

export default function FuturesLabPanel() {
  const [commodities, setCommodities] = useState<FuturesAnalysisRequest[]>([]);
  const [selected, setSelected] = useState(0);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<FuturesAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFromContract(contract: FuturesContractInput): Record<string, string> {
    const cc = contract as unknown as Record<string, number>;
    return Object.fromEntries(CONTRACT_FIELDS.map((f) => [f.key, String(cc[f.key])]));
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchFuturesSample(ctrl.signal)
      .then((s) => {
        setCommodities(s.commodities);
        if (s.commodities[0]) setFieldStr(fieldsFromContract(s.commodities[0].contract));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  function selectCommodity(i: number) {
    setSelected(i);
    if (commodities[i]) setFieldStr(fieldsFromContract(commodities[i].contract));
  }

  const request = useMemo<FuturesAnalysisRequest | null>(() => {
    const base = commodities[selected];
    if (!base) return null;
    const bc = base.contract as unknown as Record<string, number>;
    const overrides: Record<string, number> = {};
    CONTRACT_FIELDS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      overrides[f.key] = Number.isFinite(v) ? v : bc[f.key];
    });
    return {
      contract: { ...base.contract, ...overrides } as FuturesContractInput,
      curve: base.curve,
      position: base.position,
    };
  }, [commodities, selected, fieldStr]);

  const reqKey = request ? JSON.stringify(request) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeFutures(request, ctrl.signal)
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

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Futures &amp; Commodities Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const r = result;
  const nearImplConv = r?.curve_analysis.points.find((p) => p.maturity_months === 12)?.implied_convenience_yield ?? r?.curve_analysis.points[0]?.implied_convenience_yield ?? 0;
  const nearRoll = r?.roll_yield_table[0]?.roll_yield ?? 0;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Futures &amp; Commodities Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Analyze sample futures curves: cost-of-carry pricing, convenience yield,
              contango/backwardation, roll yield, calendar spreads, margin and leverage P&amp;L,
              and commodity scenario stress — all on deterministic illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Futures and commodities analytics are educational and not investment, trading, legal, tax, or risk-management advice."}
        </p>
      </div>

      {/* ── Commodity selector ───────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-1.5">
        {commodities.map((c, i) => (
          <button
            key={c.contract.symbol}
            type="button"
            onClick={() => selectCommodity(i)}
            aria-pressed={selected === i}
            className="rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors"
            style={{
              background: selected === i ? "var(--accent-softer)" : "var(--glass)",
              border: `1px solid ${selected === i ? "var(--accent-line)" : "var(--line)"}`,
              color: selected === i ? "var(--accent-text)" : "var(--text-hi)",
            }}
          >
            {c.contract.commodity_name.replace(" Sample", "")}
          </button>
        ))}
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Contract assumptions ─────────────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex items-center justify-between">
          <p className="section-title">Contract assumptions</p>
          {r && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r.commodity_summary.symbol} · carry {pct(r.commodity_summary.cost_of_carry_rate)}</span>}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {CONTRACT_FIELDS.map((f) => (
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
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Key metrics</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            <MetricCard label="Model 12M future" value={num(r.theoretical_pricing.model_futures_12m, 2)} tone="accent" />
            <MetricCard label="Curve shape" value={r.curve_analysis.curve_shape} />
            <MetricCard label="Near basis" value={num(r.curve_analysis.near_basis, 2)} />
            <MetricCard label="Implied conv. yield" value={pct(nearImplConv)} />
            <MetricCard label="Roll yield (near)" value={pct(nearRoll)} tone={nearRoll >= 0 ? "positive" : "warn"} />
            <MetricCard label="Calendar spread" value={num(r.calendar_spread_analysis.spread, 2)} />
            <MetricCard label="Initial margin" value={money(r.margin_analysis.initial_margin)} />
            <MetricCard label="Return on margin" value={pct(r.position_pnl.return_on_margin)} tone={r.position_pnl.return_on_margin >= 0 ? "positive" : "danger"} />
          </div>
        </div>
      )}

      {/* ── Futures curve table ──────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Futures curve</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Contract</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Maturity</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Observed</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Model</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Basis</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Impl. conv. yld</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Roll yield</th>
                </tr>
              </thead>
              <tbody>
                {r.curve_analysis.points.map((p) => (
                  <tr key={p.contract} style={{ borderTop: "1px solid var(--line)" }}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{p.contract}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{p.maturity_months}m</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{num(p.observed_futures, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(p.model_futures, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(p.basis) }}>{num(p.basis, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(p.implied_convenience_yield)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: p.roll_yield != null ? pnlColor(p.roll_yield) : "var(--text-mut)" }}>{p.roll_yield != null ? pct(p.roll_yield) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Curve shape + position P&L ───────────────────────────────────── */}
      {r && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Curve shape</p>
            <p className="text-lg font-bold uppercase tracking-wide" style={{ color: shapeTone(r.curve_analysis.curve_shape) }}>
              {r.curve_analysis.curve_shape}
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
              {r.curve_analysis.curve_shape === "contango"
                ? "Far contracts trade above near contracts (upward-sloping). A long holder rolling forward typically pays a negative roll yield."
                : r.curve_analysis.curve_shape === "backwardation"
                  ? "Near contracts trade above far contracts (downward-sloping). A long holder rolling forward typically earns a positive roll yield."
                  : "The curve is non-monotone (mixed), with both upward and downward segments across maturities."}
            </p>
            <p className="mt-2 text-xs" style={{ color: "var(--text-mut)" }}>
              Curve slope (far − near): <span className="mono font-semibold" style={{ color: "var(--text-hi)" }}>{num(r.curve_analysis.curve_slope, 2)}</span> · near roll yield <span className="mono font-semibold" style={{ color: pnlColor(nearRoll) }}>{pct(nearRoll)}</span>
            </p>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Position P&amp;L (sample)</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricCard label="Side" value={r.position_pnl.position_type} tone={r.position_pnl.position_type === "long" ? "positive" : "warn"} />
              <MetricCard label="Entry → Exit" value={`${num(r.position_pnl.entry_price, 2)}→${num(r.position_pnl.exit_price, 2)}`} />
              <MetricCard label="P&L" value={money(r.position_pnl.pnl)} tone={r.position_pnl.pnl >= 0 ? "positive" : "danger"} />
              <MetricCard label="Return on margin" value={pct(r.position_pnl.return_on_margin)} tone={r.position_pnl.return_on_margin >= 0 ? "positive" : "danger"} />
              <MetricCard label="Notional" value={money(r.position_pnl.notional)} />
              <MetricCard label="Initial margin" value={money(r.margin_analysis.initial_margin)} />
              <MetricCard label="Maint. margin" value={money(r.margin_analysis.maintenance_margin)} />
              <MetricCard label="Leverage" value={num(r.margin_analysis.leverage, 1) + "×"} />
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              {r.position_pnl.contracts} contract(s) × multiplier {num(r.position_pnl.contract_multiplier, 0)}. Illustrative — not a trade recommendation.
            </p>
          </div>
        </div>
      )}

      {/* ── Scenario stress ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Scenario stress</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Shocked spot</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Shape</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Near P&L</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Cal. spread P&L</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Roll yield</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Margin req</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Return on margin</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.shocked_spot, 2)}</td>
                    <td className="px-2 py-1.5 text-[11px] uppercase" style={{ color: shapeTone(s.curve_shape) }}>{s.curve_shape}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(s.near_pnl) }}>{money(s.near_pnl)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(s.calendar_spread_pnl) }}>{money(s.calendar_spread_pnl)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(s.roll_yield) }}>{pct(s.roll_yield)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{money(s.margin_requirement)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: pnlColor(s.return_on_margin) }}>{pct(s.return_on_margin)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Deterministic illustrative scenarios — not forecasts, not trading advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={FUTURES_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — not live futures or commodity prices.</li>
          <li>Cost-of-carry and curve analytics are simplified educational models, not a production risk engine.</li>
          <li>No exchange or broker integration; no margin-call simulation or mark-to-market path.</li>
          <li>Educational only — not investment, trading, legal, tax, or risk-management advice.</li>
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
