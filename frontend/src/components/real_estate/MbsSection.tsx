"use client";

/**
 * Mortgage & MBS Prepayment section (Phase 22.1) — rendered inside the Real
 * Estate Lab. Deterministic static-sample mortgage/MBS analytics: cash flows
 * with CPR/SMM/PSA prepayments, WAL, price, duration, convexity, and rate /
 * prepayment-speed stress scenarios.
 *
 * All numbers come from the backend static-sample API — no live mortgage rates,
 * no live MBS prices, educational only, not investment or lending advice.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import FormulaReference from "@/components/math/FormulaReference";
import type { FormulaGroup } from "@/components/math/formulaTypes";
import {
  analyzeMbs,
  fetchMbsSample,
  money,
  num,
  pct,
  type MbsSampleResponse,
  type MortgageMbsAnalysisResponse,
  type MortgageMbsRequest,
  type PrepaymentModel,
} from "@/lib/realEstate";

const MBS_FORMULA_GROUPS: FormulaGroup[] = [
  {
    title: "Prepayment",
    formulas: [
      { label: "CPR → SMM", latex: "\\mathrm{SMM} = 1 - (1 - \\mathrm{CPR})^{1/12}", note: "Single monthly mortality from annual CPR." },
      { label: "PSA ramp", latex: "\\mathrm{CPR}_{\\mathrm{PSA}} = \\frac{\\mathrm{PSA}}{100}\\cdot 6\\%\\cdot \\frac{\\min(\\mathrm{age},\\,30)}{30}" },
      { label: "Scheduled principal", latex: "P_{\\mathrm{sched}} = A - B_t\\cdot \\frac{c}{12}", note: "A = payment, B = balance, c = coupon." },
      { label: "Prepayment principal", latex: "P_{\\mathrm{prepay}} = \\mathrm{SMM}\\,(B_t - P_{\\mathrm{sched}})" },
    ],
  },
  {
    title: "Cash flow & valuation",
    formulas: [
      { label: "MBS cash flow", latex: "\\mathrm{CF}_t = B_t\\cdot \\frac{c_{\\mathrm{net}}}{12} + P_{\\mathrm{sched}} + P_{\\mathrm{prepay}}" },
      { label: "Weighted average life", latex: "\\mathrm{WAL} = \\frac{\\sum_t (t/12)\\, P_t}{\\sum_t P_t}" },
      { label: "Price", latex: "\\mathrm{Price} = \\sum_t \\frac{\\mathrm{CF}_t}{(1 + y/12)^t}" },
      { label: "Effective duration", latex: "D \\approx \\frac{P_- - P_+}{2 P_0\\, \\Delta y}" },
      { label: "Effective convexity", latex: "C \\approx \\frac{P_- + P_+ - 2 P_0}{P_0\\, \\Delta y^2}" },
    ],
  },
];

interface NumField {
  key: string;
  label: string;
  step: string;
  int?: boolean;
}

const POOL_FIELDS: NumField[] = [
  { key: "current_balance", label: "Current balance", step: "1000000" },
  { key: "coupon_rate", label: "Coupon rate", step: "0.0025" },
  { key: "servicing_fee_rate", label: "Servicing fee", step: "0.0005" },
  { key: "remaining_term_months", label: "Remaining term (mo)", step: "12", int: true },
  { key: "seasoning_months", label: "Seasoning (mo)", step: "6", int: true },
];
const VAL_FIELDS: NumField[] = [{ key: "discount_rate", label: "Discount rate", step: "0.0025" }];

export default function MbsSection() {
  const [sample, setSample] = useState<MbsSampleResponse | null>(null);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [model, setModel] = useState<PrepaymentModel>("psa");
  const [result, setResult] = useState<MortgageMbsAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFromSample(s: MbsSampleResponse): Record<string, string> {
    const out: Record<string, string> = {};
    const pool = s.request.pool as unknown as Record<string, number>;
    POOL_FIELDS.forEach((f) => (out[`pool.${f.key}`] = String(pool[f.key])));
    out["valuation.discount_rate"] = String(s.request.valuation.discount_rate);
    out["prepayment.psa_speed"] = String(s.request.prepayment.psa_speed ?? 100);
    out["prepayment.cpr"] = String(s.request.prepayment.cpr ?? 0.06);
    out["prepayment.prepayment_lag_months"] = String(s.request.prepayment.prepayment_lag_months);
    return out;
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchMbsSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setFieldStr(fieldsFromSample(s));
        setModel(s.request.prepayment.model);
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load MBS sample.");
      });
    return () => ctrl.abort();
  }, []);

  const request = useMemo<MortgageMbsRequest | null>(() => {
    if (!sample) return null;
    const base = sample.request;
    const parse = (k: string, fallback: number, int = false) => {
      const v = Number.parseFloat(fieldStr[k] ?? "");
      if (!Number.isFinite(v)) return fallback;
      return int ? Math.round(v) : v;
    };
    const bp = base.pool as unknown as Record<string, number>;
    const pool = { ...base.pool };
    POOL_FIELDS.forEach((f) => {
      (pool as unknown as Record<string, number>)[f.key] = parse(`pool.${f.key}`, bp[f.key], f.int);
    });
    return {
      pool,
      prepayment: {
        ...base.prepayment,
        model,
        psa_speed: model === "psa" ? parse("prepayment.psa_speed", base.prepayment.psa_speed ?? 100) : base.prepayment.psa_speed,
        cpr: model === "constant_cpr" ? parse("prepayment.cpr", base.prepayment.cpr ?? 0.06) : base.prepayment.cpr,
        prepayment_lag_months: parse("prepayment.prepayment_lag_months", base.prepayment.prepayment_lag_months, true),
      },
      valuation: { ...base.valuation, discount_rate: parse("valuation.discount_rate", base.valuation.discount_rate) },
    };
  }, [sample, fieldStr, model]);

  const reqKey = request ? JSON.stringify(request) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeMbs(request, ctrl.signal)
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
      <div className="card p-4" role="status">
        <p className="section-title">Mortgage &amp; MBS Prepayment</p>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
      </div>
    );
  }

  const numInput = (k: string, f: NumField) => (
    <label key={k} className="block">
      <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{f.label}</span>
      <input
        type="number"
        step={f.step}
        inputMode="decimal"
        aria-label={f.label}
        value={fieldStr[k] ?? ""}
        onChange={(e) => setFieldStr((s) => ({ ...s, [k]: e.target.value }))}
        className="ql-input mt-1 w-full px-2 py-1 text-sm"
      />
    </label>
  );

  const r = result;
  const m1 = r?.psa_path[0];

  return (
    <div className="space-y-5">
      {/* ── Section header ───────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Mortgage &amp; MBS Prepayment</h2>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Project mortgage cash flows with CPR/SMM and a simplified educational PSA ramp,
              decompose MBS cash flows, and compute price, WAL, duration, convexity, and
              rate / prepayment-speed stress — all on deterministic illustrative data.
            </p>
          </div>
          <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
            Static sample data
          </span>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Mortgage and MBS analytics are educational and not investment, lending, legal, tax, or valuation advice."}
        </p>
        {r && (
          <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>
            {r.pool_summary.pool_name} · net coupon {pct(r.pool_summary.net_coupon)} · factor {num(r.pool_summary.pool_factor, 3)}
          </p>
        )}
      </div>

      {analyzeError && (
        <div role="status" className="flex items-start gap-2.5 rounded-xl p-3 text-sm" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
          <span aria-hidden className="mt-0.5">⚠</span>
          <p>{analyzeError}</p>
        </div>
      )}

      {/* ── Assumptions ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="card p-4">
          <p className="section-title mb-2">Pool assumptions</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {POOL_FIELDS.map((f) => numInput(`pool.${f.key}`, f))}
          </div>
        </div>
        <div className="card p-4">
          <p className="section-title mb-2">Prepayment &amp; valuation</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <label className="block">
              <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>Model</span>
              <select aria-label="Prepayment model" value={model} onChange={(e) => setModel(e.target.value as PrepaymentModel)} className="ql-input mt-1 w-full px-2 py-1 text-sm">
                <option value="psa">PSA</option>
                <option value="constant_cpr">Constant CPR</option>
              </select>
            </label>
            {model === "psa"
              ? numInput("prepayment.psa_speed", { key: "psa_speed", label: "PSA speed", step: "25" })
              : numInput("prepayment.cpr", { key: "cpr", label: "CPR", step: "0.01" })}
            {numInput("prepayment.prepayment_lag_months", { key: "lag", label: "Prepay lag (mo)", step: "1", int: true })}
            {VAL_FIELDS.map((f) => numInput(`valuation.${f.key}`, f))}
          </div>
          {m1 && (
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Month-1 CPR {pct(m1.cpr, 2)} → SMM {pct(m1.smm, 3)} (pool age {m1.pool_age_month} mo). CPR→SMM = 1 − (1 − CPR)^(1/12).
            </p>
          )}
        </div>
      </div>

      {/* ── Key metrics ──────────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Key metrics</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            <MetricCard label="Price / 100" value={num(r.price_100, 2)} tone="accent" />
            <MetricCard label="WAL (yrs)" value={num(r.wal, 2)} />
            <MetricCard label="Duration" value={num(r.duration_convexity.duration, 2)} />
            <MetricCard label="Convexity" value={num(r.duration_convexity.convexity, 0)} />
            <MetricCard label="Total interest" value={money(r.cash_flow_summary.total_interest)} tone="positive" />
            <MetricCard label="Total principal" value={money(r.cash_flow_summary.total_principal)} />
            <MetricCard label="Final balance" value={money(r.cash_flow_summary.final_balance)} />
          </div>
          {r.duration_convexity.yield_estimate != null && (
            <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Yield to price estimate ≈ {pct(r.duration_convexity.yield_estimate)}.
            </p>
          )}
        </div>
      )}

      {/* ── Cash-flow table + PSA path ───────────────────────────────────── */}
      {r && (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">MBS cash flow — first {r.cash_flow_schedule.length} months</p>
            <div className="overflow-x-auto">
              <table className="mono w-full text-[11px]">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-1.5 py-1 text-left">Mo</th>
                    <th className="px-1.5 py-1 text-right">Beg bal</th>
                    <th className="px-1.5 py-1 text-right">Sched</th>
                    <th className="px-1.5 py-1 text-right">Prepay</th>
                    <th className="px-1.5 py-1 text-right">Interest</th>
                    <th className="px-1.5 py-1 text-right">Cash flow</th>
                    <th className="px-1.5 py-1 text-right">End bal</th>
                  </tr>
                </thead>
                <tbody>
                  {r.cash_flow_schedule.map((row) => (
                    <tr key={row.month} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-1.5 py-1" style={{ color: "var(--text-hi)" }}>{row.month}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{money(row.beginning_balance)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{money(row.scheduled_principal)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{money(row.prepayment_principal)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{money(row.interest)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-hi)" }}>{money(row.total_cash_flow)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{money(row.ending_balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">PSA / CPR path</p>
            <div className="overflow-x-auto" style={{ maxHeight: 360 }}>
              <table className="mono w-full text-[11px]">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-1.5 py-1 text-left">Mo</th>
                    <th className="px-1.5 py-1 text-right">Pool age</th>
                    <th className="px-1.5 py-1 text-right">CPR</th>
                    <th className="px-1.5 py-1 text-right">SMM</th>
                  </tr>
                </thead>
                <tbody>
                  {r.psa_path.map((p) => (
                    <tr key={p.month} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-1.5 py-1" style={{ color: "var(--text-hi)" }}>{p.month}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{p.pool_age_month}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{pct(p.cpr, 2)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{pct(p.smm, 3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
              Simplified educational PSA: 100 PSA ramps 0.2% → 6% CPR over 30 months, then flat, scaled by the PSA speed.
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
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Price / 100</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">WAL</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Duration</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Convexity</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Total interest</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Final bal</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{num(s.price_100, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.wal, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.duration, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{num(s.convexity, 0)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{money(s.total_interest)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{money(s.final_balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Faster prepayment shortens WAL; slower extends it; higher discount rate lowers price. Deterministic illustrative scenarios — not forecasts, not advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <FormulaReference title="Formulas & notes" groups={MBS_FORMULA_GROUPS} />
        <ul className="mt-3 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
          <li>Static illustrative sample data — not live mortgage rates or MBS prices.</li>
          <li>Simplified CPR/SMM/PSA model; WAL, duration, and convexity are educational approximations.</li>
          <li>Duration/convexity hold the projected cash flows fixed (not full option-adjusted/effective measures).</li>
          <li>Not a production mortgage valuation, not loan underwriting — not investment, lending, legal, or tax advice.</li>
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
