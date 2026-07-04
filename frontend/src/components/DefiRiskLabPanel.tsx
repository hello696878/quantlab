"use client";

/**
 * DeFi Yield, Stablecoin Peg & Lending Risk Lab v1 (Phase 27.0).
 *
 * Deterministic static-sample DeFi analytics: stablecoin peg deviation, lending /
 * borrow APY with a kinked utilization interest-rate model, collateral value /
 * debt / LTV / health factor, liquidation threshold and approximate liquidation
 * price, net APY / carry, a risk-regime classification, and protocol stress
 * scenarios.
 *
 * All numbers come from the backend static-sample API — no live protocol data, no
 * live crypto prices, no wallets, no blockchain RPC or smart-contract calls,
 * educational only, not investment, trading, lending, borrowing, or liquidation
 * advice, and not a production DeFi risk engine.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeDefiRisk,
  bps,
  fetchDefiRiskSample,
  hf,
  money,
  num,
  pct,
  signedBps,
  signedPct,
  type DeFiRiskAnalysisRequest,
  type DeFiRiskAnalysisResponse,
  type DeFiRiskSampleResponse,
} from "@/lib/defiRisk";

const FIELDS = [
  { key: "market_price", label: "Stable price", step: "0.001", scope: "stable" as const },
  { key: "collateral_amount", label: "Collateral qty", step: "0.1", scope: "position" as const },
  { key: "collateral_price", label: "Collateral price", step: "10", scope: "position" as const },
  { key: "debt_amount", label: "Debt amount", step: "500", scope: "position" as const },
  { key: "liquidation_threshold", label: "Liq. threshold", step: "0.01", scope: "position" as const },
  { key: "supply_apy", label: "Supply APY", step: "0.005", scope: "position" as const },
  { key: "borrow_apy", label: "Borrow APY", step: "0.005", scope: "position" as const },
];

const SAMPLE_LABELS: Record<string, string> = {
  USDC_LENDING_SAMPLE: "USDC Lending",
  USDT_PEG_STRESS_SAMPLE: "USDT Peg Stress",
  DAI_CDP_SAMPLE: "DAI Collateralized Debt",
  ETH_COLLATERAL_SAMPLE: "ETH Collateral",
  WBTC_STRESS_SAMPLE: "WBTC Stress",
};

const DEFI_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Stablecoin peg",
    formulas: [
      { label: "Peg deviation", latex: "\\mathrm{PegDeviation} = \\frac{P_{\\mathrm{stable}} - P_{\\mathrm{peg}}}{P_{\\mathrm{peg}}}" },
      { label: "Peg deviation (bps)", latex: "\\mathrm{PegDeviationBps} = \\mathrm{PegDeviation} \\times 10{,}000" },
    ],
  },
  {
    title: "Utilization & rates",
    formulas: [
      { label: "Utilization", latex: "U = \\frac{B}{S}", note: "B = total borrowed, S = total supplied." },
      { label: "Kinked borrow rate", latex: "r_b(U) = \\begin{cases} r_0 + \\frac{U}{U^*} s_1, & U \\le U^* \\\\ r_0 + s_1 + \\frac{U - U^*}{1 - U^*} s_2, & U > U^* \\end{cases}" },
      { label: "Supply rate", latex: "r_s = r_b(U)\\, U\\, (1 - \\rho)", note: "ρ = reserve factor." },
    ],
  },
  {
    title: "Collateral risk",
    formulas: [
      { label: "Collateral value", latex: "V_c = Q_c P_c" },
      { label: "Debt value", latex: "V_d = Q_d P_d" },
      { label: "Loan-to-value", latex: "\\mathrm{LTV} = \\frac{V_d}{V_c}" },
      { label: "Health factor", latex: "\\mathrm{HF} = \\frac{V_c\\, \\theta_{\\mathrm{liq}}}{V_d}", note: "θ_liq = liquidation threshold; HF < 1 means liquidatable." },
      { label: "Approx liquidation price", latex: "P_{\\mathrm{liq}} = \\frac{V_d}{Q_c\\, \\theta_{\\mathrm{liq}}}" },
      { label: "Liquidation distance", latex: "\\mathrm{LiqDistance} = \\frac{P_c - P_{\\mathrm{liq}}}{P_c}" },
    ],
  },
  {
    title: "Net APY",
    formulas: [
      { label: "Net APY / carry", latex: "\\mathrm{NetAPY} = r_{\\mathrm{supply}} - r_{\\mathrm{borrow}} - \\mathrm{fees}" },
    ],
  },
];

const REGIME_TONE: Record<string, { color: string; bg: string }> = {
  healthy: { color: "var(--emerald)", bg: "var(--accent-softer)" },
  elevated_utilization: { color: "var(--warn)", bg: "var(--warn-soft)" },
  peg_stress: { color: "var(--warn)", bg: "var(--warn-soft)" },
  liquidation_watch: { color: "var(--risk)", bg: "var(--warn-soft)" },
  protocol_stress: { color: "var(--risk)", bg: "var(--warn-soft)" },
  severe_stress: { color: "var(--risk)", bg: "var(--warn-soft)" },
};

function regimeTone(id: string): { color: string; bg: string } {
  return REGIME_TONE[id] ?? { color: "var(--text-hi)", bg: "var(--glass)" };
}

function pnlColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

function hfColor(v: number): string {
  return v < 1.0 ? "var(--risk)" : v < 1.15 ? "var(--warn)" : "var(--text-hi)";
}

const PEG_STATUS_LABEL: Record<string, string> = {
  on_peg: "On peg",
  minor_deviation: "Minor deviation",
  depegged: "Depegged",
};

export default function DefiRiskLabPanel() {
  const [sample, setSample] = useState<DeFiRiskSampleResponse | null>(null);
  const [selected, setSelected] = useState(0);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<DeFiRiskAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFrom(req: DeFiRiskAnalysisRequest): Record<string, string> {
    const out: Record<string, string> = {};
    FIELDS.forEach((f) => {
      const src = f.scope === "stable"
        ? (req.stablecoin as unknown as Record<string, number>)
        : (req.position as unknown as Record<string, number>);
      out[f.key] = String(src[f.key]);
    });
    return out;
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchDefiRiskSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSelected(0);
        setFieldStr(fieldsFrom(s.samples[0]));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const base = sample?.samples[selected] ?? null;
  function selectSample(idx: number) {
    if (!sample) return;
    setSelected(idx);
    setFieldStr(fieldsFrom(sample.samples[idx]));
  }

  const request = useMemo<DeFiRiskAnalysisRequest | null>(() => {
    if (!base) return null;
    const stableOverrides: Record<string, number> = {};
    const posOverrides: Record<string, number> = {};
    FIELDS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      const fallback = f.scope === "stable"
        ? (base.stablecoin as unknown as Record<string, number>)[f.key]
        : (base.position as unknown as Record<string, number>)[f.key];
      // debt and APYs may be zero; prices/amount/threshold must stay positive.
      const allowZero = f.key === "debt_amount" || f.key === "supply_apy" || f.key === "borrow_apy";
      const valid = Number.isFinite(v) && (allowZero ? v >= 0 : v > 0);
      const val = valid ? v : fallback;
      if (f.scope === "stable") stableOverrides[f.key] = val;
      else posOverrides[f.key] = val;
    });
    // Keep the threshold within (collateral_factor, 1] so the backend never 422s.
    const thr = Math.min(
      Math.max(posOverrides["liquidation_threshold"] ?? base.position.liquidation_threshold, base.position.collateral_factor),
      1.0,
    );
    return {
      ...base,
      stablecoin: { ...base.stablecoin, ...stableOverrides },
      position: { ...base.position, ...posOverrides, liquidation_threshold: thr },
    };
  }, [base, fieldStr]);

  const reqKey = request ? JSON.stringify([request.sample_id, request.stablecoin, request.position, request.fees_apy]) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeDefiRisk(request, ctrl.signal)
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
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>DeFi Yield, Stablecoin Peg &amp; Lending Risk Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const peg = r?.stablecoin_peg;
  const ua = r?.utilization_analysis;
  const irm = r?.interest_rate_model;
  const cr = r?.collateral_risk;
  const na = r?.net_apy_analysis;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>DeFi Yield, Stablecoin Peg &amp; Lending Risk Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Explore deterministic sample DeFi markets — stablecoin peg deviation, lending / borrow
              APY with a kinked utilization rate model, collateral value / debt / LTV / health factor,
              an approximate liquidation price, net APY carry, a risk-regime read, and protocol stress
              scenarios. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. DeFi lending, stablecoin peg, and liquidation analytics are educational and not investment, trading, lending, borrowing, liquidation, legal, tax, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Sample selector + assumptions ────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Sample &amp; assumptions</p>
          {r && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r.protocol_summary.protocol_name} · {r.protocol_summary.chain} · {r.protocol_summary.collateral_asset} → {r.protocol_summary.debt_asset}</span>}
        </div>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {sample?.samples.map((s, i) => (
            <button key={s.sample_id} type="button" onClick={() => selectSample(i)} aria-pressed={selected === i}
              className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
              style={{
                background: selected === i ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selected === i ? "var(--accent-line)" : "var(--line)"}`,
                color: selected === i ? "var(--accent-text)" : "var(--text-hi)",
              }}>{SAMPLE_LABELS[s.sample_id] ?? s.sample_id}</button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {FIELDS.map((f) => (
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
      {r && peg && ua && cr && na && (
        <div className="card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="section-title">Key metrics</p>
            <span
              className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide"
              style={{ background: regimeTone(r.risk_regime.regime_id).bg, border: "1px solid var(--line)", color: regimeTone(r.risk_regime.regime_id).color }}
              title={r.risk_regime.explanation}
            >
              {r.risk_regime.regime_label}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            <MetricCard label="Peg deviation" value={signedBps(peg.peg_deviation_bps)} tone={Math.abs(peg.peg_deviation_bps) >= 100 ? "danger" : Math.abs(peg.peg_deviation_bps) >= 20 ? "warn" : "positive"} />
            <MetricCard label="Utilization" value={pct(ua.utilization, 1)} tone={ua.utilization > ua.kink_utilization ? "warn" : "default"} />
            <MetricCard label="Borrow APY (model)" value={irm ? pct(irm.borrow_apy_model) : "—"} />
            <MetricCard label="Supply APY (model)" value={irm ? pct(irm.supply_apy_model) : "—"} />
            <MetricCard label="LTV" value={pct(cr.loan_to_value, 1)} />
            <MetricCard label="Health factor" value={hf(cr.health_factor)} tone={cr.health_factor < 1.0 ? "danger" : cr.health_factor < 1.15 ? "warn" : "positive"} />
            <MetricCard label="Liq. distance" value={bps(cr.liquidation_distance_bps)} tone="warn" />
            <MetricCard label="Net APY" value={signedPct(na.net_apy)} tone={na.net_apy >= 0 ? "positive" : "danger"} />
          </div>
        </div>
      )}

      {/* ── Peg + utilization/rate model ─────────────────────────────────── */}
      {r && peg && ua && irm && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="section-title">Stablecoin peg</p>
              <span className="mono text-[11px]" style={{ color: Math.abs(peg.peg_deviation_bps) >= 100 ? "var(--neg)" : "var(--text-faint)" }}>
                {PEG_STATUS_LABEL[peg.status] ?? peg.status}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Symbol" value={peg.symbol.replace("_SAMPLE", "")} />
              <MetricCard label="Target peg" value={num(peg.target_peg, 3)} />
              <MetricCard label="Market price" value={num(peg.market_price, 4)} tone="accent" />
              <MetricCard label="Deviation" value={signedPct(peg.peg_deviation, 3)} tone={Math.abs(peg.peg_deviation_bps) >= 100 ? "danger" : "default"} />
              <MetricCard label="Deviation (bps)" value={signedBps(peg.peg_deviation_bps)} />
              <MetricCard label="Reserve quality" value={peg.reserve_quality_score != null ? pct(peg.reserve_quality_score, 0) : "—"} />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Peg deviation = (price − peg) / peg. Reserve quality is an illustrative sample score,
              not a rating.
            </p>
          </div>

          <div className="card p-4">
            <div className="mb-2 flex items-center justify-between">
              <p className="section-title">Utilization &amp; rate model</p>
              <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{ua.utilization_regime} · kink {pct(ua.kink_utilization, 0)}</span>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Total supplied" value={money(ua.total_supplied)} />
              <MetricCard label="Total borrowed" value={money(ua.total_borrowed)} />
              <MetricCard label="Liquidity" value={money(ua.liquidity)} />
              <MetricCard label="Utilization" value={pct(ua.utilization, 1)} tone={ua.utilization > ua.kink_utilization ? "warn" : "accent"} />
              <MetricCard label="Model borrow APY" value={pct(irm.borrow_apy_model)} />
              <MetricCard label="Model supply APY" value={pct(irm.supply_apy_model)} />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Kinked model: base {pct(irm.base_rate)} · slope₁ {pct(irm.slope_1)} · slope₂ {pct(irm.slope_2)} ·
              reserve factor {pct(irm.reserve_factor, 0)}. Past the kink, rates climb the steep slope.
            </p>
          </div>
        </div>
      )}

      {/* ── Collateral risk + net APY ────────────────────────────────────── */}
      {r && cr && na && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Collateral risk</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Collateral value" value={money(cr.collateral_value)} tone="accent" />
              <MetricCard label="Debt value" value={money(cr.debt_value)} />
              <MetricCard label="LTV" value={pct(cr.loan_to_value, 1)} />
              <MetricCard label="Collateral factor" value={pct(cr.collateral_factor, 0)} />
              <MetricCard label="Liq. threshold" value={pct(cr.liquidation_threshold, 0)} />
              <MetricCard label="Health factor" value={hf(cr.health_factor)} tone={cr.health_factor < 1.0 ? "danger" : cr.health_factor < 1.15 ? "warn" : "positive"} />
              <MetricCard label="Liq. price ≈" value={num(cr.liquidation_price_approx, 2)} tone="warn" />
              <MetricCard label="Liq. distance" value={bps(cr.liquidation_distance_bps)} tone="warn" />
              <MetricCard label="Liq. penalty" value={pct(cr.liquidation_penalty, 0)} />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              HF = collateral × threshold ÷ debt; HF below 1.0 means the position is liquidatable in
              this simplified model. The liquidation price assumes only the collateral price moves —
              a coarse approximation, not a protocol's actual liquidation engine.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Net APY / carry</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <MetricCard label="Supply APY" value={pct(na.supply_apy)} tone="positive" />
              <MetricCard label="Borrow APY" value={pct(na.borrow_apy)} tone="warn" />
              <MetricCard label="Fees APY" value={pct(na.fees_apy)} />
              <MetricCard label="Net APY" value={signedPct(na.net_apy)} tone={na.net_apy >= 0 ? "positive" : "danger"} />
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {na.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
            {r.risk_regime && (
              <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Regime drivers: {r.risk_regime.drivers.join(" · ")} — {r.risk_regime.explanation}
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Scenario stress ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Protocol stress scenarios</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Peg</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Util</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Borrow APY</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">LTV</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">HF</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Liq. dist</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Net APY</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Regime</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: Math.abs(s.peg_deviation_bps) >= 100 ? "var(--neg)" : "var(--text-mut)" }}>{signedBps(s.peg_deviation_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.utilization, 0)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.borrow_apy, 1)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.loan_to_value, 0)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: hfColor(s.health_factor) }}>{hf(s.health_factor)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{bps(s.liquidation_distance_bps)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(s.net_apy) }}>{signedPct(s.net_apy, 1)}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{s.regime_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hypothetical deterministic shocks on static sample data — not forecasts, not current, and
            not lending, borrowing, trading, or liquidation advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={DEFI_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — not live protocol data, not live crypto prices, no wallets, no blockchain RPC, no smart-contract calls.</li>
          <li>The kinked rate model, health factor, and liquidation price are simplified educational approximations, not a production DeFi risk engine or a protocol's actual liquidation logic.</li>
          <li>Regime classification and stress scenarios are hypothetical — no regime or scenario is a recommendation.</li>
          <li>Educational only — not investment, trading, lending, borrowing, liquidation, legal, tax, or risk-management advice.</li>
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
