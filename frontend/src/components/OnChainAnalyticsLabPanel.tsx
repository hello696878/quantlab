"use client";

/**
 * On-Chain Flow, Exchange Reserve & Whale Concentration Lab v1 (Phase 29.0).
 *
 * Deterministic static-sample crypto on-chain analytics: exchange inflows /
 * outflows and reserve ratios, 24h activity metrics (active addresses, transfer
 * volume, transaction count, token velocity), an NVT-style valuation ratio,
 * holder-cohort distribution with a Gini-style concentration approximation,
 * whale flow pressure, an on-chain risk-regime classification, and on-chain
 * stress scenarios.
 *
 * All numbers come from the backend static-sample API — no live on-chain data,
 * no live token prices, no wallets, no blockchain RPC, smart-contract, explorer,
 * or exchange API calls, educational only, not investment, trading, or token
 * advice, and not a production due-diligence engine.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeOnChain,
  fetchOnChainSample,
  money,
  num,
  nvt,
  pct,
  signedPct,
  signedTokens,
  tokens,
  type OnChainAnalysisRequest,
  type OnChainAnalysisResponse,
  type OnChainSampleResponse,
} from "@/lib/onchainAnalytics";

const FIELDS = [
  { key: "token_price", label: "Price", step: "0.1", allowZero: false },
  { key: "circulating_supply", label: "Circ. supply", step: "1000000", allowZero: false },
  { key: "exchange_reserve_tokens", label: "Exch. reserve", step: "100000", allowZero: true },
  { key: "exchange_inflow_tokens_24h", label: "24h inflow", step: "10000", allowZero: true },
  { key: "exchange_outflow_tokens_24h", label: "24h outflow", step: "10000", allowZero: true },
  { key: "active_addresses_24h", label: "Active addresses", step: "1000", allowZero: true },
  { key: "transfer_volume_tokens_24h", label: "Transfer volume", step: "100000", allowZero: true },
];

const SAMPLE_LABELS: Record<string, string> = {
  BTC_ONCHAIN_SAMPLE: "BTC On-Chain",
  ETH_ONCHAIN_SAMPLE: "ETH On-Chain",
  L1_RESERVE_SAMPLE: "L1 Exchange Reserve",
  DEFI_WHALE_SAMPLE: "DeFi Governance Whale",
  FLOW_SAMPLE: "Exchange Inflow Stress",
};

const ONCHAIN_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Exchange flow",
    formulas: [
      { label: "Net exchange flow", latex: "\\mathrm{NetFlow} = \\mathrm{Inflow}_{ex} - \\mathrm{Outflow}_{ex}", note: "Positive = tokens moving onto exchanges." },
      { label: "Net flow % of circulating", latex: "\\mathrm{NetFlowPctCirc} = \\frac{\\mathrm{NetFlow}}{S_{\\mathrm{circ}}}" },
      { label: "Exchange reserve ratio", latex: "\\mathrm{ReserveRatio} = \\frac{R_{ex}}{S_{\\mathrm{circ}}}" },
      { label: "Reserve change approximation", latex: "\\Delta R_{ex} = \\mathrm{Inflow}_{ex} - \\mathrm{Outflow}_{ex}" },
    ],
  },
  {
    title: "Activity & valuation",
    formulas: [
      { label: "Market capitalization", latex: "\\mathrm{MarketCap} = P\\, S_{\\mathrm{circ}}" },
      { label: "Transfer velocity", latex: "\\mathrm{Velocity} = \\frac{\\mathrm{TransferVolume}_{24h}}{S_{\\mathrm{circ}}}" },
      { label: "Transfer value", latex: "\\mathrm{TransferValue}_{24h} = P \\times \\mathrm{TransferVolume}_{24h}" },
      { label: "NVT-style ratio", latex: "\\mathrm{NVT} = \\frac{\\mathrm{MarketCap}}{\\mathrm{TransferValue}_{24h}}", note: "Capped when 24h transfer value is ~zero." },
      { label: "Average transaction value", latex: "\\mathrm{AvgTxValue} = \\frac{\\mathrm{TransferVolume}_{24h}}{\\mathrm{TransactionCount}_{24h}}" },
    ],
  },
  {
    title: "Whale concentration",
    formulas: [
      { label: "Whale net flow", latex: "\\mathrm{WhaleNetFlow} = \\mathrm{WhaleInflow} - \\mathrm{WhaleOutflow}", note: "Whale inflow = deposits onto exchanges." },
      { label: "Whale net flow % of circulating", latex: "\\mathrm{WhaleNetFlowPctCirc} = \\frac{\\mathrm{WhaleNetFlow}}{S_{\\mathrm{circ}}}" },
      { label: "Concentration score", latex: "\\mathrm{ConcentrationScore} = w_1 H_{10} + w_2 H_{50} + w_3 H_{100}", note: "Documented weights w = (0.5, 0.3, 0.2)." },
    ],
  },
];

const REGIME_TONE: Record<string, { color: string; bg: string }> = {
  balanced_activity: { color: "var(--emerald)", bg: "var(--accent-softer)" },
  high_velocity_activity: { color: "var(--accent-text)", bg: "var(--accent-softer)" },
  exchange_inflow_pressure: { color: "var(--warn)", bg: "var(--warn-soft)" },
  exchange_outflow_accumulation: { color: "var(--accent-text)", bg: "var(--accent-softer)" },
  whale_concentration_risk: { color: "var(--warn)", bg: "var(--warn-soft)" },
  low_activity_high_valuation: { color: "var(--warn)", bg: "var(--warn-soft)" },
  severe_onchain_stress: { color: "var(--risk)", bg: "var(--warn-soft)" },
};

function regimeTone(id: string): { color: string; bg: string } {
  return REGIME_TONE[id] ?? { color: "var(--text-hi)", bg: "var(--glass)" };
}

function flowColor(v: number): string {
  return v > 0 ? "var(--neg)" : v < 0 ? "var(--pos)" : "var(--text-mut)";
}

export default function OnChainAnalyticsLabPanel() {
  const [sample, setSample] = useState<OnChainSampleResponse | null>(null);
  const [selected, setSelected] = useState(0);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<OnChainAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFrom(req: OnChainAnalysisRequest): Record<string, string> {
    const src = req.network as unknown as Record<string, number>;
    return Object.fromEntries(FIELDS.map((f) => [f.key, String(src[f.key])]));
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchOnChainSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setSelected(0);
        setFieldStr(fieldsFrom(s.networks[0]));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const base = sample?.networks[selected] ?? null;
  function selectSample(idx: number) {
    if (!sample) return;
    setSelected(idx);
    setFieldStr(fieldsFrom(sample.networks[idx]));
  }

  const request = useMemo<OnChainAnalysisRequest | null>(() => {
    if (!base) return null;
    const overrides: Record<string, number> = {};
    FIELDS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      const fallback = (base.network as unknown as Record<string, number>)[f.key];
      const valid = Number.isFinite(v) && (f.allowZero ? v >= 0 : v > 0);
      overrides[f.key] = valid ? v : fallback;
    });
    return { ...base, network: { ...base.network, ...overrides } };
  }, [base, fieldStr]);

  const reqKey = request ? JSON.stringify([request.network, request.whale_flow]) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeOnChain(request, ctrl.signal)
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
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>On-Chain Flow, Exchange Reserve &amp; Whale Concentration Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const ef = r?.exchange_flow;
  const am = r?.activity_metrics;
  const vm = r?.valuation_metrics;
  const wa = r?.whale_analysis;
  const ca = r?.concentration_analysis;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>On-Chain Flow, Exchange Reserve &amp; Whale Concentration Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Explore deterministic sample networks — exchange inflows/outflows and reserve ratios,
              active addresses, transfer volume and token velocity, an NVT-style valuation ratio,
              holder cohorts with a Gini-style concentration approximation, whale flows, an on-chain
              risk-regime read, and on-chain stress scenarios. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. On-chain flow, exchange reserve, whale concentration, and activity analytics are educational and not investment, trading, token, legal, tax, or risk-management advice."}
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
          <p className="section-title">Network &amp; assumptions</p>
          {r && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r.network_summary.token_name} · {r.network_summary.network_name}</span>}
        </div>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {sample?.networks.map((n, i) => (
            <button key={n.network.symbol} type="button" onClick={() => selectSample(i)} aria-pressed={selected === i}
              className="rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors"
              style={{
                background: selected === i ? "var(--accent-softer)" : "var(--glass)",
                border: `1px solid ${selected === i ? "var(--accent-line)" : "var(--line)"}`,
                color: selected === i ? "var(--accent-text)" : "var(--text-hi)",
              }}>{SAMPLE_LABELS[n.network.symbol] ?? n.network.symbol}</button>
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
      {r && ef && am && vm && wa && ca && (
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
            <MetricCard label="Reserve ratio" value={pct(ef.exchange_reserve_ratio, 1)} tone="accent" />
            <MetricCard label="Net exch. flow" value={signedTokens(ef.net_exchange_flow_tokens)} tone={ef.net_exchange_flow_tokens > 0 ? "warn" : "positive"} />
            <MetricCard label="Net flow % circ" value={signedPct(ef.net_exchange_flow_pct_circulating)} tone={Math.abs(ef.net_exchange_flow_pct_circulating) >= 0.01 ? "danger" : "default"} />
            <MetricCard label="Active addresses" value={tokens(am.active_addresses_24h)} />
            <MetricCard label="Velocity" value={num(am.token_velocity, 3)} />
            <MetricCard label="NVT ratio" value={nvt(vm.nvt_ratio)} tone={vm.nvt_ratio >= 50 ? "warn" : "default"} />
            <MetricCard label="Whale net flow" value={signedTokens(wa.whale_net_flow_tokens)} tone={wa.whale_net_flow_tokens > 0 ? "warn" : "positive"} />
            <MetricCard label="Concentration" value={num(ca.concentration_score, 2)} tone={ca.concentration_score >= 0.3 ? "warn" : "default"} />
          </div>
        </div>
      )}

      {/* ── Exchange flow + activity ─────────────────────────────────────── */}
      {r && ef && am && vm && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Exchange flow</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Exch. reserve" value={tokens(ef.exchange_reserve_tokens)} />
              <MetricCard label="Reserve value" value={money(ef.exchange_reserve_value)} />
              <MetricCard label="Reserve ratio" value={pct(ef.exchange_reserve_ratio, 1)} tone="accent" />
              <MetricCard label="24h inflow" value={tokens(ef.exchange_inflow_tokens_24h)} />
              <MetricCard label="24h outflow" value={tokens(ef.exchange_outflow_tokens_24h)} />
              <MetricCard label="Net flow" value={signedTokens(ef.net_exchange_flow_tokens)} tone={ef.net_exchange_flow_tokens > 0 ? "warn" : "positive"} />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Positive net flow = tokens moving onto exchanges (potential sell-side supply);
              negative = withdrawals. Reserve change uses the same 24h approximation.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Activity &amp; valuation</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Active addresses" value={tokens(am.active_addresses_24h)} />
              <MetricCard label="Transfer volume" value={tokens(am.transfer_volume_tokens_24h)} />
              <MetricCard label="Transfer value" value={money(am.transfer_volume_value_24h)} />
              <MetricCard label="Tx count" value={tokens(am.transaction_count_24h)} />
              <MetricCard label="Avg tx value" value={tokens(am.average_transaction_value_tokens)} />
              <MetricCard label="Velocity" value={num(am.token_velocity, 3)} tone="accent" />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Price" value={num(vm.token_price, 2)} />
              <MetricCard label="Market cap" value={money(vm.market_cap)} tone="accent" />
              <MetricCard label="NVT ratio" value={`${nvt(vm.nvt_ratio)} (${vm.nvt_status})`} tone={vm.nvt_ratio >= 50 ? "warn" : "default"} />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              NVT-style ratio = market cap ÷ 24h transfer value — a simplified valuation-vs-usage
              read, not the exact historical NVT methodology.
            </p>
          </div>
        </div>
      )}

      {/* ── Holder distribution + whale/concentration ────────────────────── */}
      {r && wa && ca && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4 xl:col-span-2">
            <p className="section-title mb-2">Holder distribution</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Cohort</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Holders</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Balance</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Share</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Avg balance</th>
                  </tr>
                </thead>
                <tbody>
                  {r.holder_distribution.map((row) => (
                    <tr key={row.cohort_name} style={{ borderTop: "1px solid var(--line)" }} title={row.description ?? undefined}>
                      <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{row.cohort_name}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{tokens(row.holder_count)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-hi)" }}>{tokens(row.token_balance)}</td>
                      <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: row.balance_share >= 0.25 ? "var(--warn)" : "var(--text-hi)" }}>{pct(row.balance_share, 1)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{tokens(row.average_balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Illustrative sample cohorts (shares of circulating supply) — not wallet-level or
              labelled on-chain data.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Whale &amp; concentration</p>
            <div className="grid grid-cols-2 gap-2">
              <MetricCard label="Whale inflow" value={tokens(wa.whale_inflow_tokens_24h)} />
              <MetricCard label="Whale outflow" value={tokens(wa.whale_outflow_tokens_24h)} />
              <MetricCard label="Whale net flow" value={signedTokens(wa.whale_net_flow_tokens)} tone={wa.whale_net_flow_tokens > 0 ? "warn" : "positive"} />
              <MetricCard label="Net % circ" value={signedPct(wa.whale_net_flow_pct_circulating)} />
              <MetricCard label="Top 10" value={pct(wa.top_10_holder_share, 0)} tone={wa.top_10_holder_share >= 0.3 ? "danger" : "default"} />
              <MetricCard label="Top 50" value={pct(wa.top_50_holder_share, 0)} />
              <MetricCard label="Top 100" value={pct(wa.top_100_holder_share, 0)} />
              <MetricCard label="Concentration" value={num(ca.concentration_score, 2)} tone={ca.concentration_score >= 0.3 ? "warn" : "positive"} />
              <MetricCard label="Gini-style" value={num(ca.gini_style_score, 3)} />
              <MetricCard label="Largest cohort" value={pct(ca.largest_cohort_share, 0)} />
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {ca.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* ── Risk regime ──────────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">On-chain risk regime</p>
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
            Deterministic educational classification on static sample data — not a signal, forecast,
            or token recommendation.
          </p>
        </div>
      )}

      {/* ── Scenario stress ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">On-chain stress scenarios</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Net flow</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">% circ</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Reserve</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Addresses</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Velocity</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">NVT</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Whale net</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Conc.</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Regime</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: flowColor(s.net_exchange_flow_tokens) }}>{signedTokens(s.net_exchange_flow_tokens)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: Math.abs(s.net_exchange_flow_pct_circulating) >= 0.01 ? "var(--neg)" : "var(--text-mut)" }}>{signedPct(s.net_exchange_flow_pct_circulating)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.exchange_reserve_ratio, 1)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{tokens(s.active_addresses_24h)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.token_velocity, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: s.nvt_ratio >= 50 ? "var(--neg)" : "var(--text-mut)" }}>{nvt(s.nvt_ratio)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: flowColor(s.whale_net_flow_tokens) }}>{signedTokens(s.whale_net_flow_tokens)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.concentration_score, 2)}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{s.regime_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hypothetical deterministic shocks on static sample data — not forecasts, not current, and
            not investment, trading, or token advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={ONCHAIN_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — not live on-chain data or token prices; no wallets, blockchain RPC, smart-contract, explorer, or exchange APIs.</li>
          <li>The NVT-style ratio, velocity, and concentration/Gini-style scores are simplified documented heuristics — not a production due-diligence engine.</li>
          <li>Regime classification and stress scenarios are hypothetical — no regime or scenario is a recommendation.</li>
          <li>Educational only — not investment, trading, token, legal, tax, or risk-management advice.</li>
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
