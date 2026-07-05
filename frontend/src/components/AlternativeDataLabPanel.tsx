"use client";

/**
 * Alternative Data, News Sentiment & Signal Decay Lab v1 (Phase 30.0).
 *
 * Deterministic static-sample alternative-data research analytics: sample
 * news/social/earnings/macro/product/supply-chain events with sentiment,
 * intensity, novelty, reliability, and relevance scores; freshness decay and a
 * leakage guard; event-study horizons; information coefficient, hit rate, and a
 * signal-decay curve; a composite alpha score; a research risk-regime read; and
 * scenario stresses.
 *
 * All numbers come from the backend static-sample API — no live news, social
 * media, or market data, no scraping, no LLM or provider APIs, educational only,
 * not investment, trading, or signal advice, and not a production alpha engine.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import ShockSlider from "@/components/controls/ShockSlider";
import { GroupedBarChart, ScenarioBarChart, SimpleLineChart } from "@/components/charts/LabCharts";
import { seriesColor } from "@/lib/chartPalette";
import {
  analyzeAlternativeData,
  corr,
  fetchAlternativeDataSample,
  num,
  pct,
  signedNum,
  signedPct,
  type AlternativeDataAnalysisRequest,
  type AlternativeDataAnalysisResponse,
  type AlternativeDataSampleResponse,
} from "@/lib/alternativeData";

const KNOBS = [
  { key: "lambda_novelty", label: "Novelty weight λ", step: "0.1" },
  { key: "gamma_freshness_per_hour", label: "Freshness decay γ (/h)", step: "0.02" },
];

// Deterministic scenario-shock sliders (client-side transforms of the sample
// events before re-analysis — no live news/social data, not advice).
const DEFAULT_SHOCKS = {
  sentiment_shock: 0,   // ± additive sentiment shift
  intensity_mult: 1,    // × event intensity
  novelty_mult: 1,      // × novelty score
  reliability_mult: 1,  // × source reliability
  lag_mult: 1,          // × publication lag
  noise_mult: 1,        // deterministic alternating return noise
  count_mult: 1,        // × event count (whole copies of the event set)
};
type ShockKey = keyof typeof DEFAULT_SHOCKS;

const HORIZONS = [1, 5, 20] as const;
type Horizon = (typeof HORIZONS)[number];

const SAMPLE_LABELS: Record<string, string> = {
  MEGACAP_NEWS_SAMPLE: "Mega Cap Equity News",
  CRYPTO_SENTIMENT_SAMPLE: "Crypto Sentiment Stress",
  EARNINGS_SURPRISE_SAMPLE: "Earnings Surprise",
  MACRO_SHOCK_SAMPLE: "Macro Shock News",
  SUPPLY_CHAIN_SAMPLE: "Supply Chain Alt Data",
};

const ALTDATA_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Weighted sentiment",
    formulas: [
      { label: "Weighted sentiment", latex: "\\mathrm{WeightedSentiment}_i = s_i I_i R_i Q_i", note: "sentiment × intensity × relevance × reliability." },
      { label: "Novelty-adjusted signal", latex: "\\mathrm{NoveltySignal}_i = \\mathrm{WeightedSentiment}_i (1 + \\lambda N_i)" },
      { label: "Freshness decay", latex: "\\mathrm{Freshness}_i = \\exp(-\\gamma \\Delta t_i)", note: "Δt = publication lag." },
      { label: "Lag-adjusted signal", latex: "\\mathrm{LagAdjustedSignal}_i = \\mathrm{NoveltySignal}_i\\, \\mathrm{Freshness}_i" },
    ],
  },
  {
    title: "Signal quality",
    formulas: [
      { label: "Alpha score", latex: "\\mathrm{AlphaScore} = \\frac{1}{N}\\sum_{i=1}^{N} \\mathrm{LagAdjustedSignal}_i" },
      { label: "Information coefficient", latex: "\\mathrm{IC} = \\mathrm{corr}(x_i, r_i)", note: "Null when a series has zero variance." },
      { label: "Hit rate", latex: "\\mathrm{HitRate} = \\frac{1}{N}\\sum_{i=1}^{N} \\mathbf{1}\\left[\\mathrm{sign}(x_i) = \\mathrm{sign}(r_i)\\right]" },
      { label: "Signal decay", latex: "\\mathrm{Decay}(h) = \\mathrm{corr}(x_i, r_{i,h})" },
    ],
  },
  {
    title: "Leakage guard",
    formulas: [
      { label: "Leakage flag", latex: "\\mathrm{LeakageFlag}_i = \\mathbf{1}\\left[t_{\\mathrm{feature},i} < t_{\\mathrm{event},i}\\right]", note: "A valid sample carries zero leakage flags." },
    ],
  },
];

const REGIME_TONE: Record<string, { color: string; bg: string }> = {
  clean_positive_signal: { color: "var(--emerald)", bg: "var(--accent-softer)" },
  clean_negative_signal: { color: "var(--accent-text)", bg: "var(--accent-softer)" },
  noisy_signal: { color: "var(--warn)", bg: "var(--warn-soft)" },
  stale_signal: { color: "var(--warn)", bg: "var(--warn-soft)" },
  low_reliability_signal: { color: "var(--warn)", bg: "var(--warn-soft)" },
  crowded_event_risk: { color: "var(--warn)", bg: "var(--warn-soft)" },
  leakage_risk: { color: "var(--risk)", bg: "var(--warn-soft)" },
  severe_altdata_stress: { color: "var(--risk)", bg: "var(--warn-soft)" },
};

function regimeTone(id: string): { color: string; bg: string } {
  return REGIME_TONE[id] ?? { color: "var(--text-hi)", bg: "var(--glass)" };
}

function sentColor(v: number): string {
  return v > 0.1 ? "var(--pos)" : v < -0.1 ? "var(--neg)" : "var(--text-mut)";
}

function pnlColor(v: number): string {
  return v > 0 ? "var(--pos)" : v < 0 ? "var(--neg)" : "var(--text-mut)";
}

const SOURCE_LABEL: Record<string, string> = {
  news: "News",
  social: "Social",
  earnings: "Earnings",
  macro: "Macro",
  product: "Product",
  regulatory: "Regulatory",
  supply_chain: "Supply chain",
};

export default function AlternativeDataLabPanel() {
  const [sample, setSample] = useState<AlternativeDataSampleResponse | null>(null);
  const [selected, setSelected] = useState(0);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<AlternativeDataAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [shock, setShock] = useState({ ...DEFAULT_SHOCKS });
  const [horizon, setHorizon] = useState<Horizon>(5);
  const setShockValue = (k: ShockKey) => (v: number) => setShock((s) => ({ ...s, [k]: v }));
  const shocksActive = (Object.keys(DEFAULT_SHOCKS) as ShockKey[]).some((k) => shock[k] !== DEFAULT_SHOCKS[k]);

  function fieldsFrom(req: AlternativeDataAnalysisRequest): Record<string, string> {
    const src = req as unknown as Record<string, number>;
    return Object.fromEntries(KNOBS.map((f) => [f.key, String(src[f.key])]));
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchAlternativeDataSample(ctrl.signal)
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
    setShock({ ...DEFAULT_SHOCKS });
  }

  const request = useMemo<AlternativeDataAnalysisRequest | null>(() => {
    if (!base) return null;
    const overrides: Record<string, number> = {};
    KNOBS.forEach((f) => {
      const v = Number.parseFloat(fieldStr[f.key] ?? "");
      const fallback = (base as unknown as Record<string, number>)[f.key];
      overrides[f.key] = Number.isFinite(v) && v >= 0 ? v : fallback;
    });

    // Apply the deterministic scenario-shock sliders (client-side, sample-only).
    const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi);
    const shocked = base.events.map((e, i) => ({
      ...e,
      sentiment_score: clamp(e.sentiment_score + shock.sentiment_shock, -1, 1),
      event_intensity: clamp(e.event_intensity * shock.intensity_mult, 0, 1),
      novelty_score: clamp(e.novelty_score * shock.novelty_mult, 0, 1),
      source_reliability: clamp(e.source_reliability * shock.reliability_mult, 0, 1),
      publication_lag_minutes: Math.max(e.publication_lag_minutes * shock.lag_mult, 0),
      observed_return_1d: e.observed_return_1d + 0.02 * (shock.noise_mult - 1) * (i % 2 === 0 ? 1 : -1),
      observed_return_5d: e.observed_return_5d + 0.02 * (shock.noise_mult - 1) * (i % 2 === 0 ? 1 : -1),
      observed_return_20d: e.observed_return_20d + 0.02 * (shock.noise_mult - 1) * (i % 2 === 0 ? 1 : -1),
    }));
    // Whole deterministic copies of the event set (ids suffixed to stay unique).
    const copies = Math.max(1, Math.round(shock.count_mult));
    const events =
      copies === 1
        ? shocked
        : Array.from({ length: copies }, (_, c) =>
            shocked.map((e) => (c === 0 ? e : { ...e, event_id: `${e.event_id}~${c + 1}` })),
          ).flat();
    return { ...base, ...overrides, events };
  }, [base, fieldStr, shock]);

  const reqKey = request
    ? JSON.stringify([request.sample_id, request.lambda_novelty, request.gamma_freshness_per_hour, shock])
    : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeAlternativeData(request, ctrl.signal)
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

  // Event timeline: day offsets on the static sample timeline (deterministic
  // parse of the fixed ISO sample timestamps — no live clock).
  const timeline = useMemo(() => {
    const rows = result?.event_table ?? [];
    if (!rows.length) return [];
    const t0 = Date.parse(rows[0].timestamp);
    return rows
      .map((e) => {
        const t = Date.parse(e.timestamp);
        if (!Number.isFinite(t) || !Number.isFinite(t0)) return null;
        return {
          x: Math.round((t - t0) / 86_400_000),
          sentiment: e.sentiment_score,
          signal: e.lag_adjusted_signal,
        };
      })
      .filter((p): p is { x: number; sentiment: number; signal: number } => p !== null)
      .sort((a, b) => a.x - b.x);
  }, [result]);

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Alternative Data, News Sentiment &amp; Signal Decay Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const sa = r?.sentiment_analysis;
  const fa = r?.freshness_analysis;
  const lg = r?.leakage_guard;
  const sq = r?.signal_quality;

  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Alternative Data, News Sentiment &amp; Signal Decay Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Explore deterministic sample event sets — weighted sentiment, novelty and freshness
              adjustments, a leakage guard, event-study horizons, information coefficient and hit
              rate, a signal-decay curve, a composite alpha score, a research risk-regime read, and
              scenario stresses. All on illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Alternative-data, sentiment, event-study, and signal-quality analytics are educational and not investment, trading, legal, tax, or risk-management advice."}
        </p>
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Sample selector + model knobs ────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Sample &amp; model assumptions</p>
          {r && <span className="mono text-[11px]" style={{ color: "var(--text-faint)" }}>{r.sample_summary.event_count} events · {r.sample_summary.symbols.join(", ")}</span>}
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
        <div className="grid grid-cols-2 gap-2 sm:max-w-md">
          {KNOBS.map((f) => (
            <label key={f.key} className="block">
              <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{f.label}</span>
              <input
                type="number"
                step={f.step}
                min="0"
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

      {/* ── Interactive scenario shocks ──────────────────────────────────── */}
      <div className="card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="section-title">Interactive scenario shocks</p>
          <div className="flex items-center gap-2">
            <div className="flex gap-1" role="group" aria-label="Return horizon">
              {HORIZONS.map((h) => (
                <button key={h} type="button" onClick={() => setHorizon(h)} aria-pressed={horizon === h}
                  className="rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors"
                  style={{
                    background: horizon === h ? "var(--accent-softer)" : "var(--glass)",
                    border: `1px solid ${horizon === h ? "var(--accent-line)" : "var(--line)"}`,
                    color: horizon === h ? "var(--accent-text)" : "var(--text-mut)",
                  }}>{h}d</button>
              ))}
            </div>
            {shocksActive && (
              <button type="button" onClick={() => setShock({ ...DEFAULT_SHOCKS })}
                className="rounded-md px-2.5 py-1 text-xs font-semibold"
                style={{ background: "var(--glass)", border: "1px solid var(--line)", color: "var(--text-hi)" }}>
                Reset shocks
              </button>
            )}
          </div>
        </div>
        <div className="grid grid-cols-1 gap-x-5 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
          <ShockSlider label="Sentiment shock" value={shock.sentiment_shock} min={-0.6} max={0.6} step={0.05}
            format={(v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}`} onChange={setShockValue("sentiment_shock")} />
          <ShockSlider label="Intensity ×" value={shock.intensity_mult} min={0} max={2} step={0.1}
            format={(v) => `${v.toFixed(1)}×`} onChange={setShockValue("intensity_mult")} />
          <ShockSlider label="Novelty ×" value={shock.novelty_mult} min={0} max={2} step={0.1}
            format={(v) => `${v.toFixed(1)}×`} onChange={setShockValue("novelty_mult")} />
          <ShockSlider label="Reliability ×" value={shock.reliability_mult} min={0} max={2} step={0.1}
            format={(v) => `${v.toFixed(1)}×`} onChange={setShockValue("reliability_mult")} />
          <ShockSlider label="Publication lag ×" value={shock.lag_mult} min={1} max={20} step={0.5}
            format={(v) => `${v.toFixed(1)}×`} onChange={setShockValue("lag_mult")} />
          <ShockSlider label="Return noise ×" value={shock.noise_mult} min={0} max={3} step={0.25}
            format={(v) => `${v.toFixed(2)}×`} onChange={setShockValue("noise_mult")} />
          <ShockSlider label="Event count ×" value={shock.count_mult} min={1} max={3} step={1}
            format={(v) => `${v.toFixed(0)}×`} onChange={setShockValue("count_mult")} />
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          Deterministic shocks applied to the static sample events before re-analysis —
          hypothetical what-ifs, not forecasts, not investment, trading, or signal advice.
        </p>
      </div>

      {/* ── Key metrics ──────────────────────────────────────────────────── */}
      {r && sa && fa && lg && sq && (
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
            <MetricCard label="Avg sentiment" value={signedNum(sa.average_sentiment, 2)} tone={sa.average_sentiment >= 0 ? "positive" : "danger"} />
            <MetricCard label="Alpha score" value={signedNum(sa.alpha_score, 4)} tone={sa.alpha_score >= 0 ? "positive" : "danger"} />
            <MetricCard label="IC (5d)" value={corr(sq.information_coefficient_5d)} tone={(sq.information_coefficient_5d ?? 0) >= 0.1 ? "positive" : "warn"} />
            <MetricCard label="Hit rate (5d)" value={pct(sq.hit_rate_5d, 0)} />
            <MetricCard label="Avg freshness" value={num(fa.average_freshness, 2)} tone={fa.average_freshness < 0.5 ? "warn" : "default"} />
            <MetricCard label="Leakage" value={String(lg.leakage_count)} tone={lg.has_leakage ? "danger" : "positive"} />
            <MetricCard label="Signal/noise" value={num(sq.signal_to_noise_score, 2)} />
            <MetricCard label="Rel-wtd quality" value={num(sq.reliability_weighted_quality, 3)} tone="accent" />
          </div>
        </div>
      )}

      {/* ── Event table ──────────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Event table</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Time</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Symbol</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Source</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Headline</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Sent.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Intens.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Novelty</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Reliab.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Fresh.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Signal</th>
                  <th className="px-2 py-1 text-center text-[11px] font-medium uppercase tracking-wide">Leak</th>
                </tr>
              </thead>
              <tbody>
                {r.event_table.map((e) => (
                  <tr key={e.event_id} style={{ borderTop: "1px solid var(--line)" }} title={`${e.headline} · r1 ${signedPct(e.observed_return_1d)} · r5 ${signedPct(e.observed_return_5d)} · r20 ${signedPct(e.observed_return_20d)}`}>
                    <td className="mono px-2 py-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>{e.timestamp.slice(5, 16).replace("T", " ")}</td>
                    <td className="mono px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{e.symbol}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{SOURCE_LABEL[e.source_type] ?? e.source_type}</td>
                    <td className="max-w-[280px] truncate px-2 py-1.5 text-[12px]" style={{ color: "var(--text-mut)" }}>{e.headline}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: sentColor(e.sentiment_score) }}>{signedNum(e.sentiment_score, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(e.event_intensity, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(e.novelty_score, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: e.source_reliability < 0.5 ? "var(--warn)" : "var(--text-mut)" }}>{num(e.source_reliability, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: e.freshness < 0.5 ? "var(--warn)" : "var(--text-mut)" }}>{num(e.freshness, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: pnlColor(e.lag_adjusted_signal) }}>{signedNum(e.lag_adjusted_signal, 3)}</td>
                    <td className="px-2 py-1.5 text-center" style={{ color: e.leakage_flag ? "var(--risk)" : "var(--text-faint)" }}>{e.leakage_flag ? "⚠" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hand-written sample events on a static January-2026 timeline — hover a row for the
            observed sample return path. Not live news, social media, or market data.
          </p>
        </div>
      )}

      {/* ── Timeline + sentiment distribution charts ─────────────────────── */}
      {r && sa && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
          <div className="card p-4 xl:col-span-2">
            <p className="section-title mb-2">Event timeline (sample days)</p>
            <SimpleLineChart
              data={timeline}
              series={[
                { key: "sentiment", label: "Sentiment", color: seriesColor(2) },
                { key: "signal", label: "Lag-adjusted signal", color: seriesColor(0) },
              ]}
              format={(v) => signedNum(v, 2)}
              formatX={(v) => `Day ${v}`}
              xLabel="sample day"
              height={200}
            />
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Per-event sentiment and lag-adjusted signal across the static sample timeline.
            </p>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Sentiment distribution</p>
            <ScenarioBarChart
              data={[
                { label: "Positive", value: sa.positive_event_count, color: "var(--emerald)" },
                { label: "Neutral", value: sa.neutral_event_count, color: seriesColor(1) },
                { label: "Negative", value: sa.negative_event_count, color: "var(--risk)" },
              ]}
              format={(v) => v.toFixed(0)}
              height={130}
            />
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Event counts by sentiment sign (|s| ≤ 0.1 counts as neutral).
            </p>
          </div>
        </div>
      )}

      {/* ── Sentiment + freshness/leakage ────────────────────────────────── */}
      {r && sa && fa && lg && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Sentiment analysis</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Avg sentiment" value={signedNum(sa.average_sentiment, 3)} tone={sa.average_sentiment >= 0 ? "positive" : "danger"} />
              <MetricCard label="Weighted avg" value={signedNum(sa.weighted_sentiment_average, 3)} />
              <MetricCard label="Alpha score" value={signedNum(sa.alpha_score, 4)} tone="accent" />
              <MetricCard label="Positive events" value={String(sa.positive_event_count)} tone="positive" />
              <MetricCard label="Negative events" value={String(sa.negative_event_count)} tone="danger" />
              <MetricCard label="Neutral events" value={String(sa.neutral_event_count)} />
            </div>
            <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Alpha score = plain average of lag-adjusted signals — a workflow illustration, not a
              production alpha signal or a recommendation.
            </p>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Freshness &amp; leakage guard</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="Avg lag" value={`${num(fa.average_publication_lag_minutes, 0)} min`} />
              <MetricCard label="Avg freshness" value={num(fa.average_freshness, 2)} tone={fa.average_freshness < 0.5 ? "warn" : "positive"} />
              <MetricCard label="Stale events" value={String(fa.stale_event_count)} tone={fa.stale_event_count > 0 ? "warn" : "default"} />
              <MetricCard label="Leakage count" value={String(lg.leakage_count)} tone={lg.has_leakage ? "danger" : "positive"} />
              <MetricCard label="Leakage rate" value={pct(lg.leakage_rate, 0)} tone={lg.has_leakage ? "danger" : "default"} />
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {fa.notes.concat(lg.notes).map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>
        </div>
      )}

      {/* ── Signal quality + event study/decay ───────────────────────────── */}
      {r && sq && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Signal quality</p>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              <MetricCard label="IC 1d" value={corr(sq.information_coefficient_1d)} tone={horizon === 1 ? "accent" : "default"} />
              <MetricCard label="IC 5d" value={corr(sq.information_coefficient_5d)} tone={horizon === 5 ? "accent" : "default"} />
              <MetricCard label="IC 20d" value={corr(sq.information_coefficient_20d)} tone={horizon === 20 ? "accent" : "default"} />
              <MetricCard label="Hit 1d" value={pct(sq.hit_rate_1d, 0)} tone={horizon === 1 ? "accent" : "default"} />
              <MetricCard label="Hit 5d" value={pct(sq.hit_rate_5d, 0)} tone={horizon === 5 ? "accent" : "default"} />
              <MetricCard label="Hit 20d" value={pct(sq.hit_rate_20d, 0)} tone={horizon === 20 ? "accent" : "default"} />
              <MetricCard label="Signal/noise" value={num(sq.signal_to_noise_score, 2)} />
              <MetricCard label="Rel-wtd quality" value={num(sq.reliability_weighted_quality, 3)} />
            </div>
            <div className="mt-3">
              <GroupedBarChart
                data={[
                  { label: "1d", ic: sq.information_coefficient_1d ?? Number.NaN, hit: sq.hit_rate_1d },
                  { label: "5d", ic: sq.information_coefficient_5d ?? Number.NaN, hit: sq.hit_rate_5d },
                  { label: "20d", ic: sq.information_coefficient_20d ?? Number.NaN, hit: sq.hit_rate_20d },
                ]}
                series={[
                  { key: "ic", label: "IC", color: seriesColor(0) },
                  { key: "hit", label: "Hit rate", color: seriesColor(2) },
                ]}
                format={(v) => v.toFixed(2)}
                height={150}
              />
            </div>
            <ul className="mt-3 list-disc space-y-1 pl-4 text-[11px]" style={{ color: "var(--text-mut)" }}>
              {sq.notes.map((n) => <li key={n}>{n}</li>)}
            </ul>
          </div>

          <div className="card p-4">
            <p className="section-title mb-2">Event study &amp; signal decay</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <SimpleLineChart
                data={r.event_study.map((p) => ({ x: p.horizon_days, ret: p.average_forward_return }))}
                series={[{ key: "ret", label: "Avg fwd return", color: seriesColor(0) }]}
                format={(v) => signedPct(v)}
                formatX={(v) => `${v}d`}
                xLabel="horizon"
                height={150}
              />
              <SimpleLineChart
                data={r.signal_decay.map((p) => ({ x: p.horizon_days, decay: p.decay_correlation ?? Number.NaN }))}
                series={[{ key: "decay", label: "Decay corr", color: seriesColor(4) }]}
                format={(v) => corr(v)}
                formatX={(v) => `${v}d`}
                xLabel="horizon"
                height={150}
              />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Horizon</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Avg fwd return</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Avg signal</th>
                    <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">IC / decay</th>
                  </tr>
                </thead>
                <tbody>
                  {r.event_study.map((p) => (
                    <tr key={p.horizon_days} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{p.horizon_days}d</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: pnlColor(p.average_forward_return) }}>{signedPct(p.average_forward_return)}</td>
                      <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{signedNum(p.average_signal, 4)}</td>
                      <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{corr(p.ic_at_horizon)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {r.signal_decay[0]?.signal_half_life_estimate != null ? (
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                Estimated signal half-life ≈ {num(r.signal_decay[0].signal_half_life_estimate, 1)} days
                (horizon where |decay| falls to half its 1-day value, linearly interpolated).
              </p>
            ) : (
              <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
                No half-life estimate — the decay correlation never falls to half its 1-day value
                inside the sample horizons.
              </p>
            )}
          </div>
        </div>
      )}

      {/* ── Risk regime ──────────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Alternative-data risk regime</p>
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
            or recommendation.
          </p>
        </div>
      )}

      {/* ── Scenario stress ──────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Alternative-data stress scenarios</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-mut)" }}>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Scenario</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Sent.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Reliab.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Fresh.</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Alpha</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">IC 5d</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Hit 5d</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Leaks</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Decay 20d</th>
                  <th className="px-2 py-1 text-left text-[11px] font-medium uppercase tracking-wide">Regime</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: sentColor(s.average_sentiment) }}>{signedNum(s.average_sentiment, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: s.average_reliability < 0.5 ? "var(--warn)" : "var(--text-mut)" }}>{num(s.average_reliability, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: s.average_freshness < 0.5 ? "var(--warn)" : "var(--text-mut)" }}>{num(s.average_freshness, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: pnlColor(s.alpha_score) }}>{signedNum(s.alpha_score, 3)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{corr(s.information_coefficient_5d)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.hit_rate_5d, 0)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: s.leakage_count > 0 ? "var(--risk)" : "var(--text-mut)" }}>{s.leakage_count}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{corr(s.decay_20d)}</td>
                    <td className="px-2 py-1.5 text-[11px]" style={{ color: "var(--text-mut)" }}>{s.regime_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Hypothetical deterministic shocks on static sample data — the leakage row is a synthetic
            violation for teaching. Not forecasts, not current, and not investment, trading, or
            signal advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={ALTDATA_FORMULA_GROUPS} collapsible />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — no live news, social media, or market data; no scraping, LLM, or data-provider APIs.</li>
          <li>Sentiment/novelty/reliability scores and return paths are hand-written sample numbers; the IC/hit-rate/decay figures illustrate the workflow, not evidence of alpha.</li>
          <li>Regime classification and stress scenarios are hypothetical — no regime or scenario is a recommendation.</li>
          <li>Educational only — not investment, trading, legal, tax, or risk-management advice, and not a production alpha engine.</li>
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
