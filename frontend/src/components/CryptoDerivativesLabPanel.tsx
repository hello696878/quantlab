"use client";

/**
 * Crypto Perpetual Futures Funding & Basis Lab v1 (Phase 26.0).
 *
 * Deterministic static-sample crypto-derivatives analytics: spot / perp / dated-
 * futures basis, funding-rate mechanics and annualized funding yield, long/short
 * funding P&L, a cash-and-carry example, position margin / liquidation
 * approximation, a funding-regime classification, and funding/basis stress
 * scenarios.
 *
 * All numbers come from the backend static-sample API — no live exchange data, no
 * live crypto prices, no broker / exchange integration, educational only, not
 * investment, trading, or liquidation advice, and not a production risk engine.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeCryptoDerivatives,
  bps,
  fetchCryptoDerivativesSample,
  money,
  num,
  pct,
  signedBps,
  signedMoney,
  signedPct,
  type CryptoDerivativesAnalysisRequest,
  type CryptoDerivativesAnalysisResponse,
  type CryptoDerivativesSampleResponse,
} from "@/lib/cryptoDerivatives";

const MARKET_FIELDS = [
  { key: "spot_price", label: "Spot", step: "1", scope: "market" as const },
  { key: "index_price", label: "Index", step: "1", scope: "market" as const },
  { key: "perp_mark_price", label: "Perp mark", step: "1", scope: "market" as const },
  { key: "funding_rate_8h", label: "Funding 8h", step: "0.0001", scope: "market" as const },
  { key: "notional", label: "Notional", step: "1000", scope: "position" as const },
  { key: "entry_price", label: "Entry", step: "1", scope: "position" as const },
  { key: "leverage", label: "Leverage", step: "1", scope: "position" as const },
  { key: "maintenance_margin_rate", label: "Maint. margin", step: "0.01", scope: "position" as const },
];

const CRYPTO_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Basis",
    formulas: [
      { label: "Perp basis", latex: "\\mathrm{Basis}_{\\mathrm{perp}} = P_{\\mathrm{perp}} - S" },
      { label: "Perp basis (bps)", latex: "\\mathrm{BasisBps}_{\\mathrm{perp}} = \\frac{P_{\\mathrm{perp}} - S}{S} \\times 10{,}000" },
      { label: "Dated futures basis", latex: "\\mathrm{Basis}_{T} = F_T - S" },
      { label: "Annualized basis", latex: "\\mathrm{AnnBasis}_{T} = \\left(\\frac{F_T}{S} - 1\\right)\\frac{365}{T_{\\mathrm{days}}}" },
    ],
  },
  {
    title: "Funding",
    formulas: [
      { label: "Compound annualized funding", latex: "\\mathrm{FundingAnnualized} = (1 + f_{8h})^{3 \\times 365} - 1" },
      { label: "Simple annualized funding", latex: "\\mathrm{FundingAnnualized}_{\\mathrm{simple}} = f_{8h} \\times 3 \\times 365" },
      { label: "Long funding P&L", latex: "\\mathrm{FundingPnL}_{\\mathrm{long}} = -\\mathrm{Notional}\\sum_{t=1}^{N} f_t" },
      { label: "Short funding P&L", latex: "\\mathrm{FundingPnL}_{\\mathrm{short}} = +\\mathrm{Notional}\\sum_{t=1}^{N} f_t" },
    ],
  },
  {
    title: "Position risk",
    formulas: [
      { label: "Long P&L", latex: "\\mathrm{PnL}_{\\mathrm{long}} = \\mathrm{Notional}\\left(\\frac{P_{\\mathrm{mark}}}{P_{\\mathrm{entry}}} - 1\\right)" },
      { label: "Short P&L", latex: "\\mathrm{PnL}_{\\mathrm{short}} = \\mathrm{Notional}\\left(1 - \\frac{P_{\\mathrm{mark}}}{P_{\\mathrm{entry}}}\\right)" },
      { label: "Initial margin", latex: "\\mathrm{IM} = \\frac{\\mathrm{Notional}}{L}" },
      { label: "Approx long liquidation", latex: "P_{\\mathrm{liq,long}} \\approx P_{\\mathrm{entry}}\\left(1 - \\frac{1}{L} + m_{\\mathrm{maint}}\\right)" },
      { label: "Approx short liquidation", latex: "P_{\\mathrm{liq,short}} \\approx P_{\\mathrm{entry}}\\left(1 + \\frac{1}{L} - m_{\\mathrm{maint}}\\right)" },
    ],
  },
  {
    title: "Carry",
    formulas: [
      { label: "Cash-and-carry gross return", latex: "\\mathrm{Carry} = \\frac{F_T - S}{S} - \\mathrm{Costs}", note: "Buy spot, sell the dated future; basis converges at expiry." },
    ],
  },
];

const REGIME_TONE: Record<string, { color: string; bg: string }> = {
  neutral: { color: "var(--text-hi)", bg: "var(--glass)" },
  basis_compressed: { color: "var(--text-hi)", bg: "var(--glass)" },
  positive_funding: { color: "var(--warn)", bg: "var(--warn-soft)" },
  negative_funding: { color: "var(--accent-text)", bg: "var(--accent-softer)" },
  basis_carry_rich: { color: "var(--emerald)", bg: "var(--accent-softer)" },
  overheated_long_perp: { color: "var(--risk)", bg: "var(--warn-soft)" },
  short_squeeze_risk: { color: "var(--risk)", bg: "var(--warn-soft)" },
};

function regimeTone(id: string): { color: string; bg: string } {
  return REGIME_TONE[id] ?? { color: "var(--text-hi)", bg: "var(--glass)" };
}

function pnlColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

export default function CryptoDerivativesLabPanel() {
  const [sample, setSample] = useState<CryptoDerivativesSampleResponse | null>(null);
  const [selected, setSelected] = useState(0);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<CryptoDerivativesAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFrom(req: CryptoDerivativesAnalysisRequest): Record<string, string> {
    const out: Record<string, string> = {};
    MARKET_FIELDS.forEach((f) => {
      const src = f.scope === "market"
        ? (req.market as unknown as Record<string, number>)
        : (req.position as unknown as Record<string, number>);
      out[f.key] = String(src[f.key]);
    });
    return out;
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchCryptoDerivativesSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSelected(0);
        setFieldStr(fieldsFrom(s.markets[0]));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const base = sample?.markets[selected] ?? null;
  function selectMarket(idx: number) {
    if (!sample) return;
    setSelected(idx);
    setFieldStr(fieldsFrom(sample.markets[idx]));
  }

  const request = useMemo<CryptoDerivativesAnalysisRequest | null>(() => {
    if (!base) return null;
    const marketOverrides: Record<string, number> = {};
    const posOverrides: Record<string, number> = {};
    MARKET_FIELDS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      const fallback = f.scope === "market"
        ? (base.market as unknown as Record<string, number>)[f.key]
        : (base.position as unknown as Record<string, number>)[f.key];
      // funding can be negative / zero; everything else must stay positive.
      const valid = f.key === "funding_rate_8h" ? Number.isFinite(v) : Number.isFinite(v) && v > 0;
      const val = valid ? v : fallback;
      if (f.scope === "market") marketOverrides[f.key] = val;
      else posOverrides[f.key] = val;
    });
    // Keep maintenance ≤ initial so the backend cross-field validator never 422s.
    const maint = Math.min(
      posOverrides["maintenance_margin_rate"] ?? base.position.maintenance_margin_rate,
      base.position.initial_margin_rate,
    );
    const market = { ...base.market, ...marketOverrides };
    const position = { ...base.position, ...posOverrides, maintenance_margin_rate: maint, mark_price: market.perp_mark_price };
    return { ...base, market, position };
  }, [base, fieldStr]);

  const reqKey = request
    ? JSON.stringify([request.market, request.position, request.funding_intervals_per_day])
    : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeCryptoDerivatives(request, ctrl.signal)
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
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Crypto Perpetual Funding &amp; Basis Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const ba = r?.basis_analysis;
  const fa = r?.funding_analysis;
  const pr = r?.position_risk;
  const ca = r?.carry_analysis;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Crypto Perpetual Funding &amp; Basis Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Explore deterministic sample crypto markets — spot / perpetual / dated-futures basis,
              funding-rate mechanics and annualized funding yield, long/short funding P&amp;L, a
              cash-and-carry example, margin / liquidation approximation, a funding-regime read, and
              funding/basis stress scenarios. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Crypto derivatives analytics are educational and not investment, trading, liquidation, legal, tax, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Market selector + assumptions ────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Market &amp; position assumptions</p>
          {pr && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r?.market_summary.symbol} · {pr.side.toUpperCase()} · {num(pr.leverage, 0)}×</span>}
        </div>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {sample?.markets.map((m, i) => (
            <button key={m.market.symbol} type="button" onClick={() => selectMarket(i)} aria-pressed={selected === i}
              className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
              style={{
                background: selected === i ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selected === i ? "var(--accent-line)" : "var(--line)"}`,
                color: selected === i ? "var(--accent-text)" : "var(--text-hi)",
              }}>{m.market.symbol.replace("_SAMPLE", "")}</button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
          {MARKET_FIELDS.map((f) => (
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
      {r && ba && fa && pr && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Key metrics</p>
            <span
              className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide"
              style={{ background: regimeTone(r.funding_regime.regime_id).bg, border: "1px solid var(--line)", color: regimeTone(r.funding_regime.regime_id).color }}
              title={r.funding_regime.explanation}
            >
              {r.funding_regime.regime_label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            <MetricCard label="Perp basis" value={signedBps(ba.perp_basis_bps)} tone={ba.perp_basis_bps >= 0 ? "positive" : "warn"} />
            <MetricCard label="Funding (ann.)" value={signedPct(fa.funding_annualized_compound)} tone={fa.funding_annualized_compound >= 0 ? "warn" : "positive"} />
            <MetricCard label="Max ann. basis" value={signedPct(ba.max_annualized_basis)} tone="accent" />
            <MetricCard label="Long funding P&L/d" value={signedMoney(fa.long_funding_pnl_daily)} tone={fa.long_funding_pnl_daily >= 0 ? "positive" : "danger"} />
            <MetricCard label="Short funding P&L/d" value={signedMoney(fa.short_funding_pnl_daily)} tone={fa.short_funding_pnl_daily >= 0 ? "positive" : "danger"} />
            <MetricCard label="Unrealized P&L" value={signedMoney(pr.unrealized_pnl)} tone={pr.unrealized_pnl >= 0 ? "positive" : "danger"} />
            <MetricCard label="Liq. distance" value={bps(pr.liquidation_distance_bps, 0)} tone="warn" />
            <MetricCard label="Curve" value={ba.curve_shape} />
          </div>
        </div>
      )}

      {/* ── Futures curve / basis + funding ──────────────────────────────── */}
      {r && fa && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4 xl:col-span-2">
            <p className="section-title mb-2">Futures curve &amp; basis</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Contract</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Maturity</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Futures</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Basis</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Basis bps</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Annualized</th>
                  </tr>
                </thead>
                <tbody>
                  {r.futures_curve.map((c) => (
                    <tr key={c.contract} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-2 py-1.5 font-semibold" style={{ color: "var(--text-hi)" }}>{c.contract}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(c.maturity_days, 0)}d</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{num(c.futures_price, 2)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(c.basis) }}>{num(c.basis, 2)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(c.basis_bps) }}>{signedBps(c.basis_bps, 0)}</td>
                      <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: pnlColor(c.annualized_basis) }}>{signedPct(c.annualized_basis)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Curve shape: <span className="font-semibold">{ba?.curve_shape}</span> · perp basis {signedBps(ba?.perp_basis_bps ?? 0)} · avg dated basis {signedBps(ba?.average_futures_basis_bps ?? 0)}.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Funding analysis</p>
            <div className="grid grid-cols-2 gap-2">
              <MetricCard label="Funding 8h" value={signedPct(fa.funding_rate_8h, 4)} />
              <MetricCard label="Next funding" value={`${num(fa.next_funding_hours, 1)}h`} />
              <MetricCard label="Simple ann." value={signedPct(fa.funding_annualized_simple)} />
              <MetricCard label="Compound ann." value={signedPct(fa.funding_annualized_compound)} tone="accent" />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              {fa.funding_rate_8h >= 0
                ? "Positive funding: longs pay shorts each interval — it is a drag on long perps and a credit to shorts."
                : "Negative funding: shorts pay longs each interval — it is a credit to long perps and a drag on shorts."}
            </p>
          </div>
        </div>
      )}

      {/* ── Position risk + carry ────────────────────────────────────────── */}
      {r && pr && ca && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Position risk ({pr.side})</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Notional" value={money(pr.notional)} />
              <MetricCard label="Leverage" value={`${num(pr.leverage, 0)}×`} />
              <MetricCard label="Initial margin" value={money(pr.initial_margin)} tone="accent" />
              <MetricCard label="Maint. margin" value={money(pr.maintenance_margin)} />
              <MetricCard label="Unrealized P&L" value={signedMoney(pr.unrealized_pnl)} tone={pr.unrealized_pnl >= 0 ? "positive" : "danger"} />
              <MetricCard label="Margin ratio" value={`${num(pr.margin_ratio, 2)}×`} tone={pr.margin_ratio >= 1 ? "positive" : "danger"} />
              <MetricCard label="Liq. price ≈" value={num(pr.liquidation_price_approx, 2)} tone="warn" />
              <MetricCard label="Liq. distance" value={bps(pr.liquidation_distance_bps, 0)} tone="warn" />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Simplified liquidation approximation on a single position — not an exchange's actual
              liquidation engine, and not liquidation advice.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Cash-and-carry</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricCard label="Best contract" value={ca.best_carry_contract} />
              <MetricCard label="Annualized basis" value={signedPct(ca.annualized_basis)} tone="accent" />
              <MetricCard label="Est. costs" value={pct(ca.estimated_costs)} />
              <MetricCard label="Gross carry" value={signedPct(ca.expected_gross_carry)} tone={ca.expected_gross_carry >= 0 ? "positive" : "warn"} />
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {ca.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* ── Scenario stress ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Funding / basis stress scenarios</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Spot</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Perp basis</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Ann. basis</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Funding (ann.)</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Position P&L</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Margin ratio</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Liq. dist</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Regime</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.shocked_spot, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(s.perp_basis_bps) }}>{signedBps(s.perp_basis_bps, 0)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(s.annualized_basis) }}>{signedPct(s.annualized_basis)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(-s.funding_annualized) }}>{signedPct(s.funding_annualized)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: pnlColor(s.position_pnl) }}>{signedMoney(s.position_pnl)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: s.margin_ratio >= 1 ? "var(--text-mut)" : "var(--neg)" }}>{num(s.margin_ratio, 2)}×</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{bps(s.liquidation_distance_bps, 0)}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{s.regime_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hypothetical deterministic shocks on static sample data — not forecasts, not current, and
            not trading or liquidation advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={CRYPTO_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — not live exchange data and not live crypto prices.</li>
          <li>Funding annualization, the carry example, and the liquidation approximation are simplified educational models, not a production risk engine.</li>
          <li>Funding-regime classification and stress scenarios are hypothetical — no regime or scenario is a recommendation.</li>
          <li>Educational only — not investment, trading, liquidation, legal, tax, or risk-management advice.</li>
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
