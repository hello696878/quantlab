"use client";

import { useEffect, useState } from "react";
import type {
  CostModel,
  CostModelType,
  PositionSizing,
  PositionSizingType,
  RiskManagement,
  RiskManagementType,
} from "@/lib/types";

// Shared, self-contained controls for the global simulation assumptions used by
// Strategy Comparison.  Each manages its own numeric *string* state (so inputs
// can be cleared / partially edited) and emits the resolved config + validity.
// No `parseFloat(value) || default` in any onChange — the raw string is stored
// and parsed only when computing the emitted config.

// Dedicated dark input primitive. This avoids browser-default white fields in
// Strategy Comparison while preserving the raw-string numeric editing model.
const inputCls = "ql-input px-2.5 py-1.5";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400">
        {label}
        {hint && <span className="ml-1 text-slate-300 normal-case">({hint})</span>}
      </span>
      {children}
    </label>
  );
}

function Segmented<T extends string>({
  options,
  value,
  onSelect,
  disabled,
}: {
  options: { id: T; label: string }[];
  value: T;
  onSelect: (id: T) => void;
  disabled?: boolean;
}) {
  return (
    <div className="ql-segmented">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(o.id)}
          className={
            "ql-segmented-option " + (value === o.id ? "active" : "")
          }
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ── Cost model ──────────────────────────────────────────────────────────────

const COST_OPTIONS: { id: CostModelType; label: string }[] = [
  { id: "simple_bps", label: "Simple BPS" },
  { id: "commission_slippage", label: "Commission + Slippage" },
  { id: "conservative", label: "Conservative" },
];

export interface CostModelControlValue {
  costModel: CostModel;
  transactionCostBps: number;
  valid: boolean;
}

export function CostModelControl({
  onChange,
  disabled,
}: {
  onChange: (v: CostModelControlValue) => void;
  disabled?: boolean;
}) {
  const [type, setType] = useState<CostModelType>("simple_bps");
  const [bps, setBps] = useState("10");
  const [commission, setCommission] = useState("5");
  const [slippage, setSlippage] = useState("5");
  const [spread, setSpread] = useState("2");

  function emit(
    t: CostModelType,
    b: string,
    c: string,
    s: string,
    sp: string,
  ) {
    const bn = parseFloat(b);
    const fallbackBps = isNaN(bn) || bn < 0 ? 10 : bn;
    if (t === "conservative") {
      onChange({ costModel: { type: "conservative" }, transactionCostBps: fallbackBps, valid: true });
      return;
    }
    if (t === "commission_slippage") {
      const cn = parseFloat(c);
      const sn = parseFloat(s);
      const spn = sp.trim() === "" ? 0 : parseFloat(sp);
      const valid =
        !isNaN(cn) && cn >= 0 && !isNaN(sn) && sn >= 0 && !isNaN(spn) && spn >= 0;
      onChange({
        costModel: {
          type: "commission_slippage",
          commission_bps: valid ? cn : 0,
          slippage_bps: valid ? sn : 0,
          spread_bps: valid ? spn : 0,
        },
        transactionCostBps: fallbackBps,
        valid,
      });
      return;
    }
    const valid = !isNaN(bn) && bn >= 0;
    onChange({
      costModel: { type: "simple_bps", transaction_cost_bps: valid ? bn : 0 },
      transactionCostBps: valid ? bn : 0,
      valid,
    });
  }

  useEffect(() => {
    emit(type, bps, commission, slippage, spread);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const eff =
    type === "conservative"
      ? 25
      : type === "commission_slippage"
        ? (isNaN(parseFloat(commission)) ? 0 : parseFloat(commission)) +
          (isNaN(parseFloat(slippage)) ? 0 : parseFloat(slippage)) +
          (spread.trim() === "" || isNaN(parseFloat(spread)) ? 0 : parseFloat(spread))
        : isNaN(parseFloat(bps))
          ? 0
          : parseFloat(bps);

  return (
    <div>
      <Segmented
        options={COST_OPTIONS}
        value={type}
        disabled={disabled}
        onSelect={(t) => {
          setType(t);
          emit(t, bps, commission, slippage, spread);
        }}
      />
      {type === "simple_bps" && (
        <div className="mt-3 grid grid-cols-3 gap-3">
          <Field label="Cost" hint="bps">
            <input
              type="number"
              className={inputCls}
              value={bps}
              min={0}
              step={1}
              disabled={disabled}
              onChange={(e) => {
                setBps(e.target.value);
                emit(type, e.target.value, commission, slippage, spread);
              }}
            />
          </Field>
        </div>
      )}
      {type === "commission_slippage" && (
        <div className="mt-3 grid grid-cols-3 gap-3">
          <Field label="Commission" hint="bps">
            <input
              type="number"
              className={inputCls}
              value={commission}
              min={0}
              step={1}
              disabled={disabled}
              onChange={(e) => {
                setCommission(e.target.value);
                emit(type, bps, e.target.value, slippage, spread);
              }}
            />
          </Field>
          <Field label="Slippage" hint="bps">
            <input
              type="number"
              className={inputCls}
              value={slippage}
              min={0}
              step={1}
              disabled={disabled}
              onChange={(e) => {
                setSlippage(e.target.value);
                emit(type, bps, commission, e.target.value, spread);
              }}
            />
          </Field>
          <Field label="Spread" hint="bps · opt">
            <input
              type="number"
              className={inputCls}
              value={spread}
              min={0}
              step={1}
              disabled={disabled}
              onChange={(e) => {
                setSpread(e.target.value);
                emit(type, bps, commission, slippage, e.target.value);
              }}
            />
          </Field>
        </div>
      )}
      {type === "conservative" && (
        <p className="mt-2 text-xs text-slate-500">Conservative preset: 10 + 10 + 5 bps.</p>
      )}
      <p className="mt-2 text-xs text-slate-600">
        Effective cost: <span className="font-semibold">{eff} bps</span> per side
      </p>
      <p className="mt-1 text-[11px] text-slate-400">
        Costs apply to turnover (long → short flips count as 2× turnover). Execution
        is simplified — no order-book depth or market impact.
      </p>
    </div>
  );
}

// ── Position sizing ─────────────────────────────────────────────────────────

const SIZING_OPTIONS: { id: PositionSizingType; label: string }[] = [
  { id: "full_allocation", label: "Full Allocation" },
  { id: "fixed_fraction", label: "Fixed Fraction" },
  { id: "volatility_target", label: "Volatility Target" },
  { id: "max_exposure", label: "Exposure Cap" },
];

export interface PositionSizingControlValue {
  positionSizing: PositionSizing | undefined;
  valid: boolean;
}

export function PositionSizingControl({
  onChange,
  disabled,
}: {
  onChange: (v: PositionSizingControlValue) => void;
  disabled?: boolean;
}) {
  const [type, setType] = useState<PositionSizingType>("full_allocation");
  const [fraction, setFraction] = useState("0.5");
  const [targetVol, setTargetVol] = useState("0.15");
  const [lookback, setLookback] = useState("20");
  const [maxExp, setMaxExp] = useState("0.8");
  const [volMaxExp, setVolMaxExp] = useState("1");

  function emit(t: PositionSizingType, f: string, tv: string, lb: string, me: string, vme: string) {
    if (t === "full_allocation") {
      onChange({ positionSizing: { type: "full_allocation" }, valid: true });
      return;
    }
    if (t === "fixed_fraction") {
      const v = parseFloat(f);
      const valid = !isNaN(v) && v > 0 && v <= 1;
      onChange({ positionSizing: { type: "fixed_fraction", fraction: valid ? v : 0.5 }, valid });
      return;
    }
    if (t === "max_exposure") {
      const v = parseFloat(me);
      const valid = !isNaN(v) && v > 0 && v <= 1;
      onChange({ positionSizing: { type: "max_exposure", max_exposure: valid ? v : 0.8 }, valid });
      return;
    }
    const tvn = parseFloat(tv);
    const lbn = parseInt(lb, 10);
    const vmen = parseFloat(vme);
    const valid =
      !isNaN(tvn) && tvn > 0 && !isNaN(lbn) && lbn >= 5 && !isNaN(vmen) && vmen > 0 && vmen <= 1;
    onChange({
      positionSizing: {
        type: "volatility_target",
        target_volatility: !isNaN(tvn) && tvn > 0 ? tvn : 0.15,
        lookback_days: !isNaN(lbn) && lbn >= 5 ? lbn : 20,
        max_exposure: !isNaN(vmen) && vmen > 0 && vmen <= 1 ? vmen : 1,
      },
      valid,
    });
  }

  useEffect(() => {
    emit(type, fraction, targetVol, lookback, maxExp, volMaxExp);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <Segmented
        options={SIZING_OPTIONS}
        value={type}
        disabled={disabled}
        onSelect={(t) => {
          setType(t);
          emit(t, fraction, targetVol, lookback, maxExp, volMaxExp);
        }}
      />
      {type === "fixed_fraction" && (
        <div className="mt-3 grid grid-cols-3 gap-3">
          <Field label="Fraction" hint="0–1">
            <input
              type="number"
              className={inputCls}
              value={fraction}
              min={0}
              max={1}
              step={0.05}
              disabled={disabled}
              onChange={(e) => {
                setFraction(e.target.value);
                emit(type, e.target.value, targetVol, lookback, maxExp, volMaxExp);
              }}
            />
          </Field>
        </div>
      )}
      {type === "max_exposure" && (
        <div className="mt-3 grid grid-cols-3 gap-3">
          <Field label="Max exposure" hint="0–1">
            <input
              type="number"
              className={inputCls}
              value={maxExp}
              min={0}
              max={1}
              step={0.05}
              disabled={disabled}
              onChange={(e) => {
                setMaxExp(e.target.value);
                emit(type, fraction, targetVol, lookback, e.target.value, volMaxExp);
              }}
            />
          </Field>
        </div>
      )}
      {type === "volatility_target" && (
        <div className="mt-3 grid grid-cols-3 gap-3">
          <Field label="Target vol" hint="e.g. 0.15">
            <input
              type="number"
              className={inputCls}
              value={targetVol}
              min={0}
              step={0.01}
              disabled={disabled}
              onChange={(e) => {
                setTargetVol(e.target.value);
                emit(type, fraction, e.target.value, lookback, maxExp, volMaxExp);
              }}
            />
          </Field>
          <Field label="Lookback" hint="≥ 5 days">
            <input
              type="number"
              className={inputCls}
              value={lookback}
              min={5}
              step={1}
              disabled={disabled}
              onChange={(e) => {
                setLookback(e.target.value);
                emit(type, fraction, targetVol, e.target.value, maxExp, volMaxExp);
              }}
            />
          </Field>
          <Field label="Max exposure" hint="0–1">
            <input
              type="number"
              className={inputCls}
              value={volMaxExp}
              min={0}
              max={1}
              step={0.05}
              disabled={disabled}
              onChange={(e) => {
                setVolMaxExp(e.target.value);
                emit(type, fraction, targetVol, lookback, maxExp, e.target.value);
              }}
            />
          </Field>
        </div>
      )}
      <p className="mt-2 text-[11px] text-slate-400">
        Sizing controls exposure after a signal — it does not change signal timing.
        Non-full allocation can reduce total return in strong bull markets. No
        leverage by default.
      </p>
    </div>
  );
}

// ── Risk management ─────────────────────────────────────────────────────────

const RISK_OPTIONS: { id: RiskManagementType; label: string }[] = [
  { id: "none", label: "None" },
  { id: "fixed_stop_take_profit", label: "Stop / Take" },
  { id: "trailing_stop", label: "Trailing" },
  { id: "max_holding_days", label: "Max Holding" },
  { id: "combined", label: "Combined" },
];

export interface RiskManagementControlValue {
  riskManagement: RiskManagement | undefined;
  valid: boolean;
}

export function RiskManagementControl({
  onChange,
  disabled,
}: {
  onChange: (v: RiskManagementControlValue) => void;
  disabled?: boolean;
}) {
  const [type, setType] = useState<RiskManagementType>("none");
  const [stop, setStop] = useState("0.1");
  const [take, setTake] = useState("0.2");
  const [trailing, setTrailing] = useState("0.1");
  const [maxHold, setMaxHold] = useState("20");

  function emit(t: RiskManagementType, sl: string, tp: string, tr: string, mh: string) {
    if (t === "none") {
      onChange({ riskManagement: { type: "none" }, valid: true });
      return;
    }
    if (t === "trailing_stop") {
      const v = parseFloat(tr);
      const valid = !isNaN(v) && v > 0 && v <= 1;
      onChange({ riskManagement: { type: "trailing_stop", trailing_stop_pct: valid ? v : 0.1 }, valid });
      return;
    }
    if (t === "max_holding_days") {
      const v = parseInt(mh, 10);
      const valid = !isNaN(v) && v >= 1;
      onChange({ riskManagement: { type: "max_holding_days", max_holding_days: valid ? v : 20 }, valid });
      return;
    }
    // fixed_stop_take_profit or combined: gather present values
    const sn = sl.trim() === "" ? null : parseFloat(sl);
    const tn = tp.trim() === "" ? null : parseFloat(tp);
    const trn = tr.trim() === "" ? null : parseFloat(tr);
    const mhn = mh.trim() === "" ? null : parseInt(mh, 10);
    const slOk = sn === null || (!isNaN(sn) && sn > 0 && sn <= 1);
    const tpOk = tn === null || (!isNaN(tn) && tn > 0);
    const trOk = trn === null || (!isNaN(trn) && trn > 0 && trn <= 1);
    const mhOk = mhn === null || (!isNaN(mhn) && mhn >= 1);
    if (t === "fixed_stop_take_profit") {
      const rm: RiskManagement = { type: "fixed_stop_take_profit" };
      if (sn !== null && slOk) rm.stop_loss_pct = sn;
      if (tn !== null && tpOk) rm.take_profit_pct = tn;
      const valid = slOk && tpOk && (sn !== null || tn !== null);
      onChange({ riskManagement: rm, valid });
      return;
    }
    // combined
    const rm: RiskManagement = { type: "combined" };
    if (sn !== null && slOk) rm.stop_loss_pct = sn;
    if (tn !== null && tpOk) rm.take_profit_pct = tn;
    if (trn !== null && trOk) rm.trailing_stop_pct = trn;
    if (mhn !== null && mhOk) rm.max_holding_days = mhn;
    const anyPresent = sn !== null || tn !== null || trn !== null || mhn !== null;
    onChange({ riskManagement: rm, valid: slOk && tpOk && trOk && mhOk && anyPresent });
  }

  useEffect(() => {
    emit(type, stop, take, trailing, maxHold);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const showStopTake = type === "fixed_stop_take_profit" || type === "combined";
  const showTrailing = type === "trailing_stop" || type === "combined";
  const showMaxHold = type === "max_holding_days" || type === "combined";

  return (
    <div>
      <Segmented
        options={RISK_OPTIONS}
        value={type}
        disabled={disabled}
        onSelect={(t) => {
          setType(t);
          emit(t, stop, take, trailing, maxHold);
        }}
      />
      {type === "none" && (
        <p className="mt-2 text-xs text-slate-500">Signal-based exits only.</p>
      )}
      {(showStopTake || showTrailing || showMaxHold) && (
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {showStopTake && (
            <>
              <Field label="Stop" hint="0.10 = 10%">
                <input
                  type="number"
                  className={inputCls}
                  value={stop}
                  min={0}
                  step={0.01}
                  disabled={disabled}
                  onChange={(e) => {
                    setStop(e.target.value);
                    emit(type, e.target.value, take, trailing, maxHold);
                  }}
                />
              </Field>
              <Field label="Take" hint="0.20 = 20%">
                <input
                  type="number"
                  className={inputCls}
                  value={take}
                  min={0}
                  step={0.01}
                  disabled={disabled}
                  onChange={(e) => {
                    setTake(e.target.value);
                    emit(type, stop, e.target.value, trailing, maxHold);
                  }}
                />
              </Field>
            </>
          )}
          {showTrailing && (
            <Field label="Trailing" hint="0.10 = 10%">
              <input
                type="number"
                className={inputCls}
                value={trailing}
                min={0}
                step={0.01}
                disabled={disabled}
                onChange={(e) => {
                  setTrailing(e.target.value);
                  emit(type, stop, take, e.target.value, maxHold);
                }}
              />
            </Field>
          )}
          {showMaxHold && (
            <Field label="Max hold" hint="bars">
              <input
                type="number"
                className={inputCls}
                value={maxHold}
                min={1}
                step={1}
                disabled={disabled}
                onChange={(e) => {
                  setMaxHold(e.target.value);
                  emit(type, stop, take, trailing, e.target.value);
                }}
              />
            </Field>
          )}
        </div>
      )}
      <p className="mt-2 text-[11px] text-slate-400">
        Risk rules close positions; they do not reverse positions by themselves.
        Daily-bar risk exits are simplified and may differ from intraday stop
        execution. They interact with transaction costs and position sizing.
      </p>
    </div>
  );
}
