"use client";

/**
 * Tokenomics, Unlock Schedule & Treasury Risk Lab v1 (Phase 28.0).
 *
 * Deterministic static-sample crypto fundamental-risk analytics: market cap /
 * FDV / float ratio, unlock schedule and dilution pressure, emission inflation
 * and a real staking-yield approximation, protocol treasury runway, holder
 * concentration, a tokenomics risk-regime classification, and unlock / treasury
 * stress scenarios.
 *
 * All numbers come from the backend static-sample API — no live token prices, no
 * live on-chain data, no wallets, no blockchain RPC or smart-contract calls,
 * educational only, not investment, trading, token, or venture advice, and not a
 * production due-diligence engine.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeTokenomics,
  fetchTokenomicsSample,
  money,
  num,
  pct,
  runway,
  signedPct,
  tokens,
  type TokenomicsAnalysisRequest,
  type TokenomicsAnalysisResponse,
  type TokenomicsSampleResponse,
} from "@/lib/tokenomics";

const FIELDS = [
  { key: "price", label: "Price", step: "0.1", allowZero: false },
  { key: "circulating_supply", label: "Circ. supply", step: "1000000", allowZero: false },
  { key: "staking_yield", label: "Staking yield", step: "0.01", allowZero: true },
  { key: "emission_rate_annual", label: "Emission rate", step: "0.01", allowZero: true },
  { key: "monthly_burn_usd", label: "Monthly burn", step: "100000", allowZero: true },
  { key: "treasury_tokens", label: "Treasury tokens", step: "1000000", allowZero: true },
  { key: "treasury_stables", label: "Treasury stables", step: "1000000", allowZero: true },
];

const SAMPLE_LABELS: Record<string, string> = {
  L1_SAMPLE: "L1 Token",
  DEFI_GOV_SAMPLE: "DeFi Governance",
  GAMING_UNLOCK_SAMPLE: "Gaming Unlock",
  STABLE_GOV_SAMPLE: "Stablecoin Governance",
  LFHV_SAMPLE: "Low Float High FDV",
};

const TOKENOMICS_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Valuation",
    formulas: [
      { label: "Market cap", latex: "\\mathrm{MarketCap} = P\\, S_{\\mathrm{circ}}" },
      { label: "Fully diluted valuation", latex: "\\mathrm{FDV} = P\\, S_{\\mathrm{total}}" },
      { label: "FDV ratio", latex: "\\mathrm{FDVRatio} = \\frac{\\mathrm{FDV}}{\\mathrm{MarketCap}}" },
      { label: "Float ratio", latex: "\\mathrm{FloatRatio} = \\frac{S_{\\mathrm{circ}}}{S_{\\mathrm{total}}}" },
    ],
  },
  {
    title: "Unlocks",
    formulas: [
      { label: "Unlock value", latex: "\\mathrm{UnlockValue}_i = P\\, U_i" },
      { label: "Unlock % of circulating", latex: "\\mathrm{UnlockPctCirc}_i = \\frac{U_i}{S_{\\mathrm{circ}}}" },
      { label: "Unlock pressure", latex: "\\mathrm{UnlockPressure} = \\frac{\\sum_{i \\in H} U_i}{S_{\\mathrm{circ}}}", note: "H = the unlock horizon (e.g. next 180 days)." },
    ],
  },
  {
    title: "Emissions & staking",
    formulas: [
      { label: "Annual emission", latex: "E_{\\mathrm{annual}} = S_{\\mathrm{circ}}\\, e" },
      { label: "Emission inflation", latex: "\\mathrm{EmissionInflation} = \\frac{E_{\\mathrm{annual}}}{S_{\\mathrm{circ}}}" },
      { label: "Real yield approximation", latex: "\\mathrm{RealYield} = y_{\\mathrm{staking}} - \\mathrm{EmissionInflation}" },
    ],
  },
  {
    title: "Treasury",
    formulas: [
      { label: "Treasury value", latex: "\\mathrm{TreasuryValue} = P\\, S_{\\mathrm{treasury}} + \\mathrm{TreasuryStables}" },
      { label: "Runway months", latex: "\\mathrm{RunwayMonths} = \\frac{\\mathrm{TreasuryValue}}{\\mathrm{MonthlyBurn}}" },
      { label: "Revenue-adjusted runway", latex: "\\mathrm{RunwayAdj} = \\frac{\\mathrm{TreasuryValue}}{\\max(\\mathrm{MonthlyBurn} - \\mathrm{MonthlyRevenue},\\, \\epsilon)}" },
    ],
  },
];

const REGIME_TONE: Record<string, { color: string; bg: string }> = {
  balanced: { color: "var(--emerald)", bg: "var(--accent-softer)" },
  low_float_high_fdv: { color: "var(--warn)", bg: "var(--warn-soft)" },
  unlock_pressure: { color: "var(--warn)", bg: "var(--warn-soft)" },
  emission_pressure: { color: "var(--warn)", bg: "var(--warn-soft)" },
  treasury_runway_risk: { color: "var(--risk)", bg: "var(--warn-soft)" },
  concentration_risk: { color: "var(--warn)", bg: "var(--warn-soft)" },
  severe_tokenomics_stress: { color: "var(--risk)", bg: "var(--warn-soft)" },
};

function regimeTone(id: string): { color: string; bg: string } {
  return REGIME_TONE[id] ?? { color: "var(--text-hi)", bg: "var(--glass)" };
}

function pnlColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

export default function TokenomicsLabPanel() {
  const [sample, setSample] = useState<TokenomicsSampleResponse | null>(null);
  const [selected, setSelected] = useState(0);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<TokenomicsAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFrom(req: TokenomicsAnalysisRequest): Record<string, string> {
    const src = req.market as unknown as Record<string, number | null | undefined>;
    return Object.fromEntries(FIELDS.map((f) => [f.key, String(src[f.key] ?? 0)]));
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchTokenomicsSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSelected(0);
        setFieldStr(fieldsFrom(s.tokens[0]));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const base = sample?.tokens[selected] ?? null;
  function selectToken(idx: number) {
    if (!sample) return;
    setSelected(idx);
    setFieldStr(fieldsFrom(sample.tokens[idx]));
  }

  const request = useMemo<TokenomicsAnalysisRequest | null>(() => {
    if (!base) return null;
    const overrides: Record<string, number> = {};
    FIELDS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      const fallback = (base.market as unknown as Record<string, number | null>)[f.key] ?? 0;
      const valid = Number.isFinite(v) && (f.allowZero ? v >= 0 : v > 0);
      overrides[f.key] = valid ? v : (fallback as number);
    });
    // Keep circulating ≤ total supply so the backend cross-field check never 422s.
    const circ = Math.min(overrides["circulating_supply"], base.market.total_supply);
    return {
      ...base,
      market: { ...base.market, ...overrides, circulating_supply: circ },
    };
  }, [base, fieldStr]);

  const reqKey = request ? JSON.stringify([request.market, request.holder_concentration]) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeTokenomics(request, ctrl.signal)
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
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Tokenomics, Unlock Schedule &amp; Treasury Risk Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const v = r?.valuation_metrics;
  const up = r?.unlock_pressure;
  const em = r?.emission_analysis;
  const st = r?.staking_analysis;
  const tr = r?.treasury_analysis;
  const hc = r?.holder_concentration;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Tokenomics, Unlock Schedule &amp; Treasury Risk Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Explore deterministic sample tokens — market cap vs FDV, float ratio, unlock schedules
              and dilution pressure, emission inflation and a real staking-yield approximation,
              treasury runway, holder concentration, a tokenomics risk-regime read, and unlock /
              treasury stress scenarios. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Tokenomics, unlock, treasury, and concentration analytics are educational and not investment, trading, token, venture, legal, tax, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Token selector + assumptions ─────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Token &amp; assumptions</p>
          {r && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r.token_summary.token_name}</span>}
        </div>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {sample?.tokens.map((t, i) => (
            <button key={t.market.symbol} type="button" onClick={() => selectToken(i)} aria-pressed={selected === i}
              className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
              style={{
                background: selected === i ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selected === i ? "var(--accent-line)" : "var(--line)"}`,
                color: selected === i ? "var(--accent-text)" : "var(--text-hi)",
              }}>{SAMPLE_LABELS[t.market.symbol] ?? t.market.symbol}</button>
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
      {r && v && up && em && st && tr && hc && (
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
            <MetricCard label="Market cap" value={money(v.market_cap)} tone="accent" />
            <MetricCard label="FDV" value={money(v.fully_diluted_valuation)} />
            <MetricCard label="FDV / MC" value={`${num(v.fdv_to_market_cap, 2)}×`} tone={v.fdv_to_market_cap >= 5 ? "warn" : "default"} />
            <MetricCard label="Float ratio" value={pct(v.float_ratio, 0)} tone={v.float_ratio <= 0.25 ? "warn" : "default"} />
            <MetricCard label="180d unlock" value={pct(up.next_180d_pct_circulating, 1)} tone={up.next_180d_pct_circulating >= 0.15 ? "danger" : "default"} />
            <MetricCard label="Real yield ≈" value={signedPct(st.real_yield_approx)} tone={st.real_yield_approx >= 0 ? "positive" : "danger"} />
            <MetricCard label="Runway" value={runway(tr.runway_months)} tone={tr.runway_months < 12 ? "danger" : "positive"} />
            <MetricCard label="Concentration" value={num(hc.concentration_score, 2)} tone={hc.concentration_score >= 0.3 ? "warn" : "default"} />
          </div>
        </div>
      )}

      {/* ── Unlock schedule + pressure ───────────────────────────────────── */}
      {r && up && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4 xl:col-span-2">
            <p className="section-title mb-2">Unlock schedule</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Date</th>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Category</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Tokens</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Value</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">% circ</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Cum %</th>
                  </tr>
                </thead>
                <tbody>
                  {r.unlock_schedule.map((row) => (
                    <tr key={`${row.date}-${row.category}`} style={{ borderTop: "1px solid var(--line)" }} title={row.description ?? undefined}>
                      <td className="mono px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row.date}</td>
                      <td className="px-2 py-1.5" style={{ color: "var(--text-mut)" }}>{row.category}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{tokens(row.tokens)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{money(row.unlock_value)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: row.unlock_pct_circulating >= 0.10 ? "var(--neg)" : "var(--text-mut)" }}>{pct(row.unlock_pct_circulating, 1)}</td>
                      <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{pct(row.cumulative_unlock_pct_circulating, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Deterministic sample day offsets — unlocks are potential new float, not a forecast of selling.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Unlock pressure</p>
            <div className="grid grid-cols-2 gap-2">
              <MetricCard label="Next 30d" value={tokens(up.next_30d_tokens)} />
              <MetricCard label="Next 90d" value={tokens(up.next_90d_tokens)} />
              <MetricCard label="Next 180d" value={tokens(up.next_180d_tokens)} />
              <MetricCard label="Next 365d" value={tokens(up.next_365d_tokens)} />
              <MetricCard label="180d % circ" value={pct(up.next_180d_pct_circulating, 1)} tone={up.next_180d_pct_circulating >= 0.15 ? "danger" : "accent"} />
              <MetricCard label="Pressure score" value={num(up.pressure_score, 2)} tone={up.pressure_score >= 0.5 ? "danger" : up.pressure_score >= 0.25 ? "warn" : "positive"} />
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {up.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* ── Emission / staking + treasury ────────────────────────────────── */}
      {r && em && st && tr && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Emissions &amp; staking</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Emission rate" value={pct(em.emission_rate_annual)} />
              <MetricCard label="Annual emission" value={tokens(em.annual_emission_tokens)} />
              <MetricCard label="Emission value" value={money(em.annual_emission_value)} />
              <MetricCard label="Emission inflation" value={pct(em.emission_inflation)} tone={em.emission_inflation >= 0.10 ? "warn" : "default"} />
              <MetricCard label="Staking yield" value={pct(st.staking_yield)} tone="positive" />
              <MetricCard label="Real yield ≈" value={signedPct(st.real_yield_approx)} tone={st.real_yield_approx >= 0 ? "positive" : "danger"} />
            </div>
            {st.protocol_revenue_yield != null && (
              <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Protocol revenue yield ≈ {pct(st.protocol_revenue_yield)} of market cap (illustrative sample revenue).
              </p>
            )}
            <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {st.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Treasury runway</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Treasury tokens" value={money(tr.treasury_token_value)} />
              <MetricCard label="Treasury stables" value={money(tr.treasury_stables)} />
              <MetricCard label="Total treasury" value={money(tr.treasury_total_value)} tone="accent" />
              <MetricCard label="Monthly burn" value={money(tr.monthly_burn_usd)} />
              <MetricCard label="Monthly revenue" value={money(tr.monthly_revenue_usd)} />
              <MetricCard label="Runway" value={runway(tr.runway_months)} tone={tr.runway_months < 12 ? "danger" : "positive"} />
              <MetricCard label="Rev-adj. runway" value={runway(tr.revenue_adjusted_runway_months)} />
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {tr.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* ── Holder concentration + regime ────────────────────────────────── */}
      {r && hc && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Holder concentration</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Top 1" value={pct(hc.top_1_holder_share, 0)} tone={hc.top_1_holder_share >= 0.20 ? "danger" : "default"} />
              <MetricCard label="Top 5" value={pct(hc.top_5_holder_share, 0)} />
              <MetricCard label="Top 10" value={pct(hc.top_10_holder_share, 0)} tone={hc.top_10_holder_share >= 0.60 ? "danger" : "default"} />
              {hc.insider_share != null && <MetricCard label="Insiders" value={pct(hc.insider_share, 0)} />}
              {hc.foundation_share != null && <MetricCard label="Foundation" value={pct(hc.foundation_share, 0)} />}
              {hc.community_share != null && <MetricCard label="Community" value={pct(hc.community_share, 0)} />}
              <MetricCard label="Concentration score" value={num(hc.concentration_score, 2)} tone={hc.concentration_score >= 0.3 ? "warn" : "positive"} />
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {hc.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Tokenomics risk regime</p>
            <div className="flex items-center gap-3">
              <span
                className="rounded-full px-3 py-1 text-[12px] font-semibold uppercase tracking-wide"
                style={{ background: regimeTone(r.risk_regime.regime_id).bg, border: "1px solid var(--line)", color: regimeTone(r.risk_regime.regime_id).color }}
              >
                {r.risk_regime.regime_label}
              </span>
              <span className="mono text-sm" style={{ color: "var(--text-mut)" }}>score {num(r.risk_regime.score, 2)}</span>
            </div>
            <p className="mt-3 text-sm" style={{ color: "var(--text-hi)" }}>{r.risk_regime.explanation}</p>
            <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {r.risk_regime.drivers.map((d) => <li key={d}>{d}</li>)}
            </ul>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Deterministic educational classification on static sample data — not a rating, forecast,
              or token recommendation.
            </p>
          </div>
        </div>
      )}

      {/* ── Scenario stress ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Unlock / treasury stress scenarios</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Price</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Mkt cap</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">180d unlock</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Infl.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Real yield</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Treasury</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Runway</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Conc.</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Regime</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.price, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{money(s.market_cap)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: s.next_180d_unlock_pressure >= 0.15 ? "var(--neg)" : "var(--text-mut)" }}>{pct(s.next_180d_unlock_pressure, 1)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.emission_inflation, 0)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(s.real_yield_approx) }}>{signedPct(s.real_yield_approx, 1)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{money(s.treasury_value)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: s.runway_months < 12 ? "var(--neg)" : "var(--text-mut)" }}>{runway(s.runway_months)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.concentration_score, 2)}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{s.regime_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hypothetical deterministic shocks on static sample data — not forecasts, not current, and
            not investment, trading, token, or venture advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={TOKENOMICS_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — not live token prices, not live on-chain data, no wallets, no blockchain RPC, no smart-contract calls.</li>
          <li>Unlock schedules use deterministic sample day offsets; unlock pressure is potential new float, not a selling forecast.</li>
          <li>The real-yield approximation, treasury runway, and concentration/pressure scores are simplified documented heuristics — not a production due-diligence engine.</li>
          <li>Educational only — not investment, trading, token, venture, legal, tax, or risk-management advice.</li>
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
