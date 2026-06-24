"use client";

/**
 * Real Estate Lab v1 (Phase 22.0).
 *
 * Deterministic static-sample income-property + REIT analytics: NOI, cap rate,
 * valuation, mortgage amortization, LTV/DSCR, levered cash flow (cash-on-cash,
 * IRR, equity multiple), rent/vacancy/cap/rate stress scenarios, and a simple
 * REIT NAV discount/premium example.
 *
 * All numbers come from the backend static-sample API — no live property/REIT
 * data, educational only, not investment / tax / legal / lending advice.
 */

import { useEffect, useMemo, useState } from "react";
import MetricCard from "@/components/MetricCard";
import {
  analyzeRealEstate,
  fetchRealEstateSample,
  money,
  num,
  pct,
  type DebtInput,
  type PropertyInput,
  type RealEstateAnalysisResponse,
  type ReitInput,
  type SampleResponse,
} from "@/lib/realEstate";

type FieldKind = "money" | "rate" | "int";
interface FieldDef {
  key: string;
  label: string;
  step: string;
  kind: FieldKind;
}

const PROPERTY_FIELDS: FieldDef[] = [
  { key: "purchase_price", label: "Purchase price", step: "10000", kind: "money" },
  { key: "gross_rent_annual", label: "Gross rent (annual)", step: "5000", kind: "money" },
  { key: "other_income_annual", label: "Other income (annual)", step: "1000", kind: "money" },
  { key: "vacancy_rate", label: "Vacancy rate", step: "0.01", kind: "rate" },
  { key: "operating_expenses_annual", label: "Operating expenses (annual)", step: "5000", kind: "money" },
  { key: "capex_reserve_annual", label: "CapEx reserve (annual)", step: "1000", kind: "money" },
  { key: "purchase_costs", label: "Purchase costs", step: "5000", kind: "money" },
  { key: "exit_cap_rate", label: "Exit cap rate", step: "0.0025", kind: "rate" },
  { key: "holding_period_years", label: "Holding period (yrs)", step: "1", kind: "int" },
];
const DEBT_FIELDS: FieldDef[] = [
  { key: "loan_amount", label: "Loan amount", step: "50000", kind: "money" },
  { key: "interest_rate", label: "Interest rate", step: "0.0025", kind: "rate" },
  { key: "amortization_years", label: "Amortization (yrs)", step: "1", kind: "int" },
  { key: "term_years", label: "Term (yrs)", step: "1", kind: "int" },
];
const REIT_FIELDS: FieldDef[] = [
  { key: "property_nav", label: "Property NAV", step: "10000000", kind: "money" },
  { key: "net_debt", label: "Net debt", step: "10000000", kind: "money" },
  { key: "shares_outstanding", label: "Shares outstanding", step: "1000000", kind: "int" },
  { key: "share_price", label: "Share price", step: "0.5", kind: "money" },
  { key: "funds_from_operations", label: "FFO (annual)", step: "1000000", kind: "money" },
  { key: "dividend_per_share", label: "Dividend / share", step: "0.05", kind: "money" },
];

function color(v: number, good = true): string {
  if (v === 0) return "var(--text-mut)";
  return (v > 0) === good ? "var(--pos)" : "var(--neg)";
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1" style={{ borderTop: "1px solid var(--line)" }}>
      <span className="text-xs" style={{ color: "var(--text-mut)" }}>{label}</span>
      <span className={"mono text-sm" + (strong ? " font-bold" : " font-medium")} style={{ color: "var(--text-hi)" }}>{value}</span>
    </div>
  );
}

export default function RealEstateLabPanel() {
  const [sample, setSample] = useState<SampleResponse | null>(null);
  const [fieldStr, setFieldStr] = useState<Record<string, string>>({});
  const [result, setResult] = useState<RealEstateAnalysisResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  function fieldsFromSample(s: SampleResponse): Record<string, string> {
    const out: Record<string, string> = {};
    const prop = s.request.property as unknown as Record<string, number>;
    const debt = s.request.debt as unknown as Record<string, number>;
    const reit = s.request.reit as unknown as Record<string, number>;
    PROPERTY_FIELDS.forEach((f) => (out[`property.${f.key}`] = String(prop[f.key])));
    DEBT_FIELDS.forEach((f) => (out[`debt.${f.key}`] = String(debt[f.key])));
    REIT_FIELDS.forEach((f) => (out[`reit.${f.key}`] = String(reit[f.key])));
    return out;
  }

  useEffect(() => {
    const ctrl = new AbortController();
    fetchRealEstateSample(ctrl.signal)
      .then((s) => {
        setSample(s);
        setFieldStr(fieldsFromSample(s));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setLoadError(e instanceof Error ? e.message : "Failed to load sample.");
      });
    return () => ctrl.abort();
  }, []);

  const request = useMemo(() => {
    if (!sample) return null;
    const base = sample.request;
    const parse = (group: string, key: string, fallback: number) => {
      const v = Number.parseFloat(fieldStr[`${group}.${key}`] ?? "");
      return Number.isFinite(v) ? v : fallback;
    };
    const bp = base.property as unknown as Record<string, number>;
    const bd = base.debt as unknown as Record<string, number>;
    const br = base.reit as unknown as Record<string, number>;
    const propOv: Record<string, number> = {};
    PROPERTY_FIELDS.forEach((f) => (propOv[f.key] = parse("property", f.key, bp[f.key])));
    const debtOv: Record<string, number> = {};
    DEBT_FIELDS.forEach((f) => (debtOv[f.key] = parse("debt", f.key, bd[f.key])));
    const reitOv: Record<string, number> = {};
    REIT_FIELDS.forEach((f) => (reitOv[f.key] = parse("reit", f.key, br[f.key])));
    return {
      property: { ...base.property, ...propOv } as PropertyInput,
      debt: { ...base.debt, ...debtOv } as DebtInput,
      reit: { ...base.reit, ...reitOv } as ReitInput,
      selling_cost_rate: base.selling_cost_rate,
    };
  }, [sample, fieldStr]);

  const reqKey = request ? JSON.stringify(request) : "";
  useEffect(() => {
    if (!request) return;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => {
      analyzeRealEstate(request, ctrl.signal)
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

  function resetSample() {
    if (sample) setFieldStr(fieldsFromSample(sample));
  }

  function FieldGrid({ title, fields, group }: { title: string; fields: FieldDef[]; group: string }) {
    return (
      <div className="card p-4">
        <p className="section-title mb-2">{title}</p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {fields.map((f) => (
            <label key={f.key} className="block">
              <span className="text-[10px] font-medium uppercase tracking-wide" style={{ color: "var(--text-mut)" }}>{f.label}</span>
              <input
                type="number"
                step={f.step}
                inputMode="decimal"
                aria-label={f.label}
                value={fieldStr[`${group}.${f.key}`] ?? ""}
                onChange={(e) => setFieldStr((s) => ({ ...s, [`${group}.${f.key}`]: e.target.value }))}
                className="ql-input mt-1 w-full px-2 py-1 text-sm"
              />
            </label>
          ))}
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="card p-6" role="status">
        <h1 className="text-xl font-bold" style={{ color: "var(--text-hi)" }}>Real Estate Lab</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--warn)" }}>{loadError}</p>
        <p className="mt-1 text-xs" style={{ color: "var(--text-mut)" }}>
          This lab uses the backend static-sample analytics API. Start the QuantLab API and reopen the lab.
        </p>
      </div>
    );
  }

  const r = result;
  return (
    <div className="space-y-5">
      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <div className="card panel-glow p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-extrabold tracking-[-0.01em]" style={{ color: "var(--text-hi)" }}>Real Estate Lab</h1>
            <p className="mt-1 max-w-2xl text-sm" style={{ color: "var(--text-mut)" }}>
              Analyze a sample income property: NOI, cap rate, mortgage debt service, DSCR,
              cash-on-cash, IRR, equity multiple, rent/vacancy/cap/rate stress scenarios, and a
              simple REIT NAV discount/premium — all on deterministic illustrative data.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide" style={{ background: "var(--warn-soft)", border: "1px solid var(--line)", color: "var(--warn)" }}>
              Static sample data
            </span>
            <button type="button" onClick={resetSample} className="rounded-md px-2.5 py-1 text-xs font-medium" style={{ border: "1px solid var(--line)", color: "var(--text-mut)" }}>
              Reset sample
            </button>
          </div>
        </div>
        <p className="mt-3 text-[11px]" style={{ color: "var(--text-faint)" }}>
          {r?.disclaimer ?? "Static illustrative sample data. Real-estate analytics are educational and not investment, tax, legal, or lending advice."}
        </p>
        {r && (
          <p className="mt-1 text-[11px]" style={{ color: "var(--text-mut)" }}>
            {r.property_summary.property_name} · {r.property_summary.property_type} · {r.property_summary.market}
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
      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <FieldGrid title="Property assumptions" fields={PROPERTY_FIELDS} group="property" />
        <div className="space-y-5">
          <FieldGrid title="Debt assumptions" fields={DEBT_FIELDS} group="debt" />
          <FieldGrid title="REIT assumptions" fields={REIT_FIELDS} group="reit" />
        </div>
      </div>

      {/* ── Key metrics ──────────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">Key metrics</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
            <MetricCard label="NOI" value={money(r.income_statement.net_operating_income)} tone="accent" />
            <MetricCard label="In-place cap rate" value={pct(r.valuation.in_place_cap_rate)} />
            <MetricCard label="Value @ exit cap" value={money(r.valuation.value_at_exit_cap)} />
            <MetricCard label="LTV" value={pct(r.debt_metrics.loan_to_value)} />
            <MetricCard label="DSCR" value={num(r.debt_metrics.dscr, 2) + "×"} tone={r.debt_metrics.dscr >= 1.2 ? "positive" : "warn"} />
            <MetricCard label="Cash-on-cash" value={pct(r.levered_returns.cash_on_cash)} tone={r.levered_returns.cash_on_cash >= 0 ? "positive" : "danger"} />
            <MetricCard label="IRR (base)" value={r.levered_returns.irr != null ? pct(r.levered_returns.irr) : "n/a"} tone="accent" />
            <MetricCard label="Equity multiple" value={num(r.levered_returns.equity_multiple, 2) + "×"} />
          </div>
          {r.levered_returns.irr == null && r.levered_returns.irr_note && (
            <p className="mt-1.5 text-[11px]" style={{ color: "var(--text-faint)" }}>{r.levered_returns.irr_note}</p>
          )}
        </div>
      )}

      {/* ── Income statement + debt ──────────────────────────────────────── */}
      {r && (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <div className="card p-4">
            <p className="section-title mb-2">Income statement (year 1)</p>
            <Row label="Gross rent" value={money(r.income_statement.gross_rent)} />
            <Row label="Vacancy loss" value={"−" + money(r.income_statement.vacancy_loss)} />
            <Row label="Other income" value={money(r.income_statement.other_income)} />
            <Row label="Effective gross income" value={money(r.income_statement.effective_gross_income)} strong />
            <Row label="Operating expenses" value={"−" + money(r.income_statement.operating_expenses)} />
            <Row label="Net operating income (NOI)" value={money(r.income_statement.net_operating_income)} strong />
            <Row label="CapEx reserve" value={"−" + money(r.income_statement.capex_reserve)} />
            <Row label="NOI after reserves" value={money(r.income_statement.noi_after_reserves)} strong />
          </div>
          <div className="card p-4">
            <p className="section-title mb-2">Debt &amp; amortization</p>
            <div className="grid grid-cols-2 gap-2">
              <MetricCard label="Monthly payment" value={money(r.debt_metrics.monthly_payment)} />
              <MetricCard label="Annual debt service" value={money(r.debt_metrics.annual_debt_service)} />
              <MetricCard label="DSCR" value={num(r.debt_metrics.dscr, 2) + "×"} tone={r.debt_metrics.dscr >= 1.2 ? "positive" : "warn"} />
              <MetricCard label="Balance @ exit" value={money(r.debt_metrics.remaining_balance_at_exit)} />
            </div>
            <p className="section-title mb-1 mt-3">Amortization — first 12 months</p>
            <div className="overflow-x-auto">
              <table className="mono w-full text-[11px]">
                <thead>
                  <tr style={{ color: "var(--text-mut)" }}>
                    <th className="px-1.5 py-1 text-left">Mo</th>
                    <th className="px-1.5 py-1 text-right">Payment</th>
                    <th className="px-1.5 py-1 text-right">Interest</th>
                    <th className="px-1.5 py-1 text-right">Principal</th>
                    <th className="px-1.5 py-1 text-right">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {r.amortization_schedule.map((row) => (
                    <tr key={row.month} style={{ borderTop: "1px solid var(--line)" }}>
                      <td className="px-1.5 py-1" style={{ color: "var(--text-hi)" }}>{row.month}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{money(row.payment)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{money(row.interest)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-mut)" }}>{money(row.principal)}</td>
                      <td className="px-1.5 py-1 text-right" style={{ color: "var(--text-hi)" }}>{money(row.balance)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Vacancy</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Exit cap</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Rate</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">NOI (yr 1)</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">DSCR</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Cash-on-cash</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Exit value</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">Equity ×</th>
                  <th className="px-2 py-1 text-right text-[11px] font-medium uppercase tracking-wide">IRR</th>
                </tr>
              </thead>
              <tbody>
                {r.scenario_results.map((s) => (
                  <tr key={s.id} style={{ borderTop: "1px solid var(--line)" }} title={s.description}>
                    <td className="px-2 py-1.5" style={{ color: "var(--text-hi)" }}>{s.name}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.vacancy_rate, 1)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.exit_cap_rate, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{pct(s.interest_rate, 2)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{money(s.noi)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: color(s.dscr - 1.2) }}>{num(s.dscr, 2)}×</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: color(s.cash_on_cash) }}>{pct(s.cash_on_cash)}</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: "var(--text-mut)" }}>{money(s.exit_value)}</td>
                    <td className="mono px-2 py-1.5 text-right font-semibold" style={{ color: "var(--text-hi)" }}>{num(s.equity_multiple, 2)}×</td>
                    <td className="mono px-2 py-1.5 text-right" style={{ color: color(s.irr ?? 0) }}>{s.irr != null ? pct(s.irr) : "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Deterministic illustrative scenarios — not forecasts, not advice.
          </p>
        </div>
      )}

      {/* ── REIT NAV ─────────────────────────────────────────────────────── */}
      {r && (
        <div className="card p-4">
          <p className="section-title mb-2">REIT NAV analysis (simplified example)</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <MetricCard label="NAV / share" value={money(r.reit_nav_analysis.nav_per_share)} tone="accent" />
            <MetricCard label="Share price" value={money(r.reit_nav_analysis.share_price)} />
            <MetricCard label="Premium / discount" value={pct(r.reit_nav_analysis.premium_discount)} tone={r.reit_nav_analysis.premium_discount < 0 ? "warn" : "positive"} />
            <MetricCard label="FFO / share" value={money(r.reit_nav_analysis.ffo_per_share)} />
            <MetricCard label="P / FFO" value={r.reit_nav_analysis.p_ffo != null ? num(r.reit_nav_analysis.p_ffo, 1) + "×" : "n/a"} />
            <MetricCard label="Dividend yield" value={pct(r.reit_nav_analysis.dividend_yield)} tone="positive" />
          </div>
          <p className="mt-2 text-[11px]" style={{ color: "var(--text-faint)" }}>
            Simplified illustrative REIT example — not live REIT prices, not investment advice.
          </p>
        </div>
      )}

      {/* ── Formulas & notes ─────────────────────────────────────────────── */}
      <div className="card p-4">
        <p className="section-title mb-2">Formulas &amp; notes</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ul className="mono space-y-1 text-[11px]" style={{ color: "var(--text-hi)" }}>
            <li>EGI = gross_rent · (1 − vacancy) + other_income</li>
            <li>NOI = EGI − operating_expenses</li>
            <li>cap_rate = NOI ÷ property_value</li>
            <li>value = NOI ÷ cap_rate</li>
            <li>LTV = loan_amount ÷ purchase_price</li>
            <li>payment = P·rₘ ÷ (1 − (1+rₘ)⁻ⁿ)</li>
          </ul>
          <ul className="mono space-y-1 text-[11px]" style={{ color: "var(--text-hi)" }}>
            <li>DSCR = NOI ÷ annual_debt_service</li>
            <li>cash-on-cash = before-tax CF ÷ initial_equity</li>
            <li>equity_multiple = total_distributions ÷ initial_equity</li>
            <li>IRR: rate where NPV(cash_flows) = 0</li>
            <li>NAV/share = (property_NAV − net_debt) ÷ shares</li>
            <li>premium/discount = price ÷ NAV/share − 1</li>
          </ul>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>Why this matters</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
              <li>NOI and cap rate translate income into a property value independent of financing.</li>
              <li>DSCR and LTV summarise leverage risk — lenders watch both closely.</li>
              <li>Cash-on-cash, IRR, and equity multiple measure levered equity returns over the hold.</li>
              <li>The REIT NAV example shows how a share can trade at a premium or discount to net asset value.</li>
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold" style={{ color: "var(--text-hi)" }}>Limitations</p>
            <ul className="mt-1 list-disc space-y-1 pl-4 text-xs" style={{ color: "var(--text-mut)" }}>
              <li>Static illustrative sample data — not live property or REIT prices.</li>
              <li>Simplified deterministic model — not a production appraisal or loan-underwriting system.</li>
              <li>No taxes, depreciation, financing fees beyond points, or detailed reserves modelling.</li>
              <li>Educational only — not investment, tax, legal, or lending advice.</li>
            </ul>
          </div>
        </div>
        {r?.notes && (
          <ul className="mt-3 space-y-1 text-[11px]" style={{ color: "var(--text-faint)" }}>
            {r.notes.map((n) => <li key={n}>• {n}</li>)}
          </ul>
        )}
      </div>
    </div>
  );
}
