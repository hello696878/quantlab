"""
Observation models for the cost diagnostics lab.

Two observation types are supported and never mixed inside one run:

* ``trade`` — round-trip trades with explicit entry/exit prices, quantity and
  an explicit contract multiplier.  Monetary values are primary; return views
  are derived from entry notional.
* ``period`` — per-period return observations with explicit turnover (fraction
  of capital traded that period).  Return values are primary; no monetary view
  is fabricated because period observations carry no capital base.

Hard rules: unique ids, deterministic ordering, finite values, tz-consistent
timestamps, exit never before entry, one shared currency (no silent FX
conversion), no fabricated trade size, no hidden multiplier (the default
multiplier of 1.0 is echoed back explicitly on every normalized trade).
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

OBSERVATION_TYPES = ("trade", "period")
SIDES = ("long", "short")

MIN_OBSERVATIONS = 2
MAX_OBSERVATIONS = 2000
MAX_CANDIDATES = 16
MAX_ID_LENGTH = 64
DEFAULT_CURRENCY = "USD"

# Per-observation liquidity / execution inputs that cost models may consume.
LIQUIDITY_INPUT_KEYS = ("spread", "adv", "volume", "volatility", "realized_slippage")
SPREAD_INPUT_UNITS = ("bps", "price", "ticks")
ADV_INPUT_UNITS = ("units", "currency")
INPUT_BASES = (
    "supplied_realized", "trailing", "dataset_lineage",
    "declared", "full_sample", "unknown",
)


class CostInputError(ValueError):
    """Raised when supplied observations or inputs violate the contract."""


def _finite(value: Any, field: str, *, positive: bool = False,
            non_negative: bool = False) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise CostInputError(f"{field} must be a finite number")
    if isinstance(value, bool) or not math.isfinite(f):
        raise CostInputError(f"{field} must be a finite number")
    if positive and f <= 0:
        raise CostInputError(f"{field} must be > 0")
    if non_negative and f < 0:
        raise CostInputError(f"{field} must be >= 0")
    return f


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CostInputError(f"{field} must be a non-empty string")
    out = value.strip()
    if len(out) > MAX_ID_LENGTH:
        raise CostInputError(f"{field} must be at most {MAX_ID_LENGTH} characters")
    return out


def parse_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CostInputError(f"{field} must be an ISO-8601 timestamp string")
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        raise CostInputError(f"{field} is not a valid ISO-8601 timestamp: {value!r}")


def _check_tz_consistency(stamps: List[datetime], context: str) -> None:
    if not stamps:
        return
    has_tz = stamps[0].tzinfo is not None
    for s in stamps:
        if (s.tzinfo is not None) != has_tz:
            raise CostInputError(
                f"{context}: timestamps mix timezone-aware and naive values")


def _normalize_liquidity_inputs(raw: Any, obs_ref: str) -> Dict[str, Any]:
    """Validate optional per-observation execution inputs with provenance."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise CostInputError(f"{obs_ref}: cost_inputs must be an object")
    out: Dict[str, Any] = {}
    for key, spec in raw.items():
        if key not in LIQUIDITY_INPUT_KEYS:
            raise CostInputError(
                f"{obs_ref}: unsupported cost input {key!r}; supported: "
                f"{', '.join(LIQUIDITY_INPUT_KEYS)}")
        if not isinstance(spec, dict):
            raise CostInputError(f"{obs_ref}: cost input {key!r} must be an object")
        entry: Dict[str, Any] = {}
        # realized slippage is the only input allowed to be negative
        # (favourable fills exist only when supplied and labelled as realized).
        if key == "realized_slippage":
            entry["value"] = _finite(spec.get("value"), f"{obs_ref}:{key}.value")
        else:
            entry["value"] = _finite(spec.get("value"), f"{obs_ref}:{key}.value",
                                     non_negative=True)
        if key == "spread":
            unit = spec.get("unit")
            if unit not in SPREAD_INPUT_UNITS:
                raise CostInputError(
                    f"{obs_ref}: spread input unit must be one of "
                    f"{', '.join(SPREAD_INPUT_UNITS)}")
            entry["unit"] = unit
        elif key in ("adv", "volume"):
            unit = spec.get("unit")
            if unit not in ADV_INPUT_UNITS:
                raise CostInputError(
                    f"{obs_ref}: {key} input unit must be 'units' or 'currency'")
            entry["unit"] = unit
        basis = spec.get("basis", "unknown")
        if key == "realized_slippage":
            basis = spec.get("basis", "supplied_realized")
            if basis != "supplied_realized":
                raise CostInputError(
                    f"{obs_ref}: realized_slippage basis must be 'supplied_realized'")
        if basis not in INPUT_BASES:
            raise CostInputError(
                f"{obs_ref}: {key} basis must be one of {', '.join(INPUT_BASES)}")
        entry["basis"] = basis
        window = spec.get("window", "trailing")
        if window not in ("trailing", "centered"):
            raise CostInputError(
                f"{obs_ref}: {key} window must be 'trailing' or 'centered'")
        entry["window"] = window
        for int_field in ("lag", "lookback"):
            if spec.get(int_field) is not None:
                v = spec[int_field]
                if isinstance(v, bool) or not isinstance(v, int):
                    raise CostInputError(
                        f"{obs_ref}: {key} {int_field} must be an integer")
                entry[int_field] = v
        out[key] = entry
    return out


def _normalize_metadata(raw: Any, obs_ref: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict) or len(raw) > 16:
        raise CostInputError(f"{obs_ref}: metadata must be an object with <= 16 keys")
    out = {}
    for k, v in raw.items():
        if not isinstance(k, str) or len(k) > 64:
            raise CostInputError(f"{obs_ref}: metadata keys must be short strings")
        if isinstance(v, bool) or isinstance(v, (int, str)):
            out[k] = v if not isinstance(v, str) else v[:256]
        elif isinstance(v, float):
            if not math.isfinite(v):
                raise CostInputError(f"{obs_ref}: metadata values must be finite")
            out[k] = v
        elif v is None:
            out[k] = None
        else:
            raise CostInputError(f"{obs_ref}: metadata values must be scalars")
    return out


def normalize_trades(raw: Any) -> Tuple[List[Dict[str, Any]], str]:
    """Validate and deterministically order trade-level observations.

    Returns ``(trades, currency)``.  Gross PnL is taken as supplied when
    present (source ``supplied``); otherwise it is derived from prices via the
    documented transformation ``direction * (exit - entry) * quantity *
    multiplier`` (source ``derived_from_prices``).  Quantity is never inferred
    from PnL.
    """
    if not isinstance(raw, list):
        raise CostInputError("trades must be a list")
    if not (MIN_OBSERVATIONS <= len(raw) <= MAX_OBSERVATIONS):
        raise CostInputError(
            f"trades must contain between {MIN_OBSERVATIONS} and "
            f"{MAX_OBSERVATIONS} entries")
    trades: List[Dict[str, Any]] = []
    ids = set()
    currencies = set()
    stamps: List[datetime] = []
    for i, t in enumerate(raw):
        if not isinstance(t, dict):
            raise CostInputError(f"trade[{i}] must be an object")
        trade_id = _identifier(t.get("trade_id"), f"trade[{i}].trade_id")
        if trade_id in ids:
            raise CostInputError(f"duplicate trade_id {trade_id!r}")
        ids.add(trade_id)
        ref = f"trade {trade_id}"
        candidate_id = _identifier(t.get("candidate_id"), f"{ref}: candidate_id")
        side = t.get("side")
        if side not in SIDES:
            raise CostInputError(f"{ref}: side must be 'long' or 'short'")
        entry_ts = parse_timestamp(t.get("entry_timestamp"), f"{ref}: entry_timestamp")
        exit_ts = parse_timestamp(t.get("exit_timestamp"), f"{ref}: exit_timestamp")
        if (entry_ts.tzinfo is None) != (exit_ts.tzinfo is None):
            raise CostInputError(
                f"{ref}: timestamps mix timezone-aware and naive values")
        if exit_ts < entry_ts:
            raise CostInputError(f"{ref}: exit_timestamp is before entry_timestamp")
        stamps.extend([entry_ts, exit_ts])
        entry_price = _finite(t.get("entry_price"), f"{ref}: entry_price", positive=True)
        exit_price = _finite(t.get("exit_price"), f"{ref}: exit_price", positive=True)
        quantity = _finite(t.get("quantity"), f"{ref}: quantity", positive=True)
        multiplier = 1.0
        if t.get("contract_multiplier") is not None:
            multiplier = _finite(t.get("contract_multiplier"),
                                 f"{ref}: contract_multiplier", positive=True)
        currency = t.get("currency", DEFAULT_CURRENCY)
        if not isinstance(currency, str) or not (1 <= len(currency.strip()) <= 8):
            raise CostInputError(f"{ref}: currency must be a short string")
        currencies.add(currency.strip().upper())

        direction = 1.0 if side == "long" else -1.0
        derived_pnl = direction * (exit_price - entry_price) * quantity * multiplier
        warnings: List[str] = []
        if t.get("gross_pnl") is not None:
            gross_pnl = _finite(t.get("gross_pnl"), f"{ref}: gross_pnl")
            source = "supplied"
            tol = 1e-6 * max(1.0, abs(derived_pnl))
            if abs(gross_pnl - derived_pnl) > max(tol, 1e-9):
                warnings.append(
                    "supplied gross_pnl differs from the price-derived value; "
                    "the supplied value is used")
        else:
            gross_pnl = derived_pnl
            source = "derived_from_prices"

        entry_notional = entry_price * quantity * multiplier
        exit_notional = exit_price * quantity * multiplier
        traded_notional = entry_notional + exit_notional
        gross_return = gross_pnl / entry_notional
        for derived_name, derived_value in (
                ("gross_pnl", gross_pnl), ("entry_notional", entry_notional),
                ("exit_notional", exit_notional),
                ("traded_notional", traded_notional),
                ("gross_return", gross_return)):
            if not math.isfinite(derived_value):
                raise CostInputError(
                    f"{ref}: derived {derived_name} is not finite "
                    "(inputs are too extreme)")
        holding_days = (exit_ts - entry_ts).total_seconds() / 86400.0

        trades.append({
            "_sort_key": entry_ts,
            "observation_id": trade_id,
            "trade_id": trade_id,
            "candidate_id": candidate_id,
            "instrument": (t.get("instrument") or "")[:32],
            "side": side,
            "entry_timestamp": t["entry_timestamp"].strip(),
            "exit_timestamp": t["exit_timestamp"].strip(),
            "timestamp": t["entry_timestamp"].strip(),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "quantity": quantity,
            "contract_multiplier": multiplier,
            "currency": currency.strip().upper(),
            "gross_pnl": gross_pnl,
            "gross_pnl_source": source,
            "gross_return": gross_return,
            "entry_notional": entry_notional,
            "exit_notional": exit_notional,
            "traded_notional": traded_notional,
            "holding_period_days": round(holding_days, 6),
            "cost_inputs": _normalize_liquidity_inputs(t.get("cost_inputs"), ref),
            "metadata": _normalize_metadata(t.get("metadata"), ref),
            "input_warnings": warnings,
        })
    _check_tz_consistency(stamps, "trades")
    if len(currencies) > 1:
        raise CostInputError(
            "mixed trade currencies are not supported; supply one currency "
            "per run (no silent FX conversion)")
    candidates = {t["candidate_id"] for t in trades}
    if len(candidates) > MAX_CANDIDATES:
        raise CostInputError(f"at most {MAX_CANDIDATES} candidates are supported")
    # chronological ordering on the PARSED timestamps — a lexicographic
    # string sort would misorder heterogeneous UTC offsets
    trades.sort(key=lambda t: (t.pop("_sort_key"), t["trade_id"]))
    return trades, (currencies.pop() if currencies else DEFAULT_CURRENCY)


def normalize_period_observations(raw: Any) -> List[Dict[str, Any]]:
    """Validate and deterministically order period-level observations."""
    if not isinstance(raw, list):
        raise CostInputError("observations must be a list")
    if not (MIN_OBSERVATIONS <= len(raw) <= MAX_OBSERVATIONS):
        raise CostInputError(
            f"observations must contain between {MIN_OBSERVATIONS} and "
            f"{MAX_OBSERVATIONS} entries")
    out: List[Dict[str, Any]] = []
    ids = set()
    stamps: List[datetime] = []
    for i, o in enumerate(raw):
        if not isinstance(o, dict):
            raise CostInputError(f"observation[{i}] must be an object")
        obs_id = _identifier(o.get("observation_id"), f"observation[{i}].observation_id")
        if obs_id in ids:
            raise CostInputError(f"duplicate observation_id {obs_id!r}")
        ids.add(obs_id)
        ref = f"observation {obs_id}"
        candidate_id = _identifier(o.get("candidate_id"), f"{ref}: candidate_id")
        ts = parse_timestamp(o.get("timestamp"), f"{ref}: timestamp")
        stamps.append(ts)
        gross_return = _finite(o.get("gross_return"), f"{ref}: gross_return")
        turnover = None
        if o.get("turnover") is not None:
            turnover = _finite(o.get("turnover"), f"{ref}: turnover", non_negative=True)
        traded_notional = None
        if o.get("traded_notional") is not None:
            traded_notional = _finite(o.get("traded_notional"),
                                      f"{ref}: traded_notional", non_negative=True)
        out.append({
            "_sort_key": ts,
            "observation_id": obs_id,
            "candidate_id": candidate_id,
            "timestamp": o["timestamp"].strip(),
            "gross_return": gross_return,
            "turnover": turnover,
            "traded_notional": traded_notional,
            "cost_inputs": _normalize_liquidity_inputs(o.get("cost_inputs"), ref),
            "metadata": _normalize_metadata(o.get("metadata"), ref),
            "input_warnings": [],
        })
    _check_tz_consistency(stamps, "observations")
    candidates = {o["candidate_id"] for o in out}
    if len(candidates) > MAX_CANDIDATES:
        raise CostInputError(f"at most {MAX_CANDIDATES} candidates are supported")
    # chronological ordering on the parsed timestamps (see normalize_trades)
    out.sort(key=lambda o: (o.pop("_sort_key"), o["observation_id"]))
    return out
