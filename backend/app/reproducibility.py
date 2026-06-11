"""
Reproducible backtest config hashing (research v1).

Every single-asset backtest (and Strategy Comparison run) gets a deterministic
**config hash**: SHA-256 over a canonical JSON form of the *result-changing
inputs*.  Same normalized config → same hash; different result-changing config
→ different hash.

Canonicalization rules
----------------------
* Inputs only — never outputs (metrics, curves, trades, warnings, timestamps,
  database ids) and never display-only state (theme, tabs, zoom).
* Missing optional engines normalize to their defaults before hashing, and
  settings that resolve to the same engine behaviour hash identically:
  - no cost model / legacy ``transaction_cost_bps`` ≡ ``simple_bps`` at the
    same effective per-side bps (the engine only sees ``effective_cost_bps``);
  - missing position sizing ≡ ``full_allocation`` (legacy ``full`` alias too);
  - missing risk management ≡ ``none``;
  - missing annualization ≡ ``trading_days_252``; ``auto`` hashes as its
    *resolved* convention (auto-on-SPY ≡ explicit 252 — identical results);
  - missing benchmark ≡ ``buy_and_hold_same_asset``.
* Object keys sorted recursively; compact JSON; floats that are whole numbers
  serialize as ints (10.0 ≡ 10); tickers uppercased; ``None`` values dropped.

Honest limits (documented, not hidden): the hash identifies **input
assumptions**.  It cannot guarantee identical future output if the external
data provider revises history — pair it with the data-quality metadata when
auditing.  CSV backtests additionally include a SHA-256 fingerprint of the
uploaded file content when available.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from app.schemas import (
    BenchmarkConfig,
    CostModel,
    PositionSizing,
    Reproducibility,
    RiskManagement,
)

SCHEMA_VERSION = "backtest_config_v1"
COMPARISON_SCHEMA_VERSION = "comparison_config_v1"
SHORT_HASH_LEN = 12


def _norm_number(value: float) -> Any:
    """10.0 and 10 mean the same thing — canonicalize whole floats to ints."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _normalize(obj: Any) -> Any:
    """Recursively drop Nones, normalize numbers, and sort dict keys."""
    if isinstance(obj, dict):
        return {
            k: _normalize(v)
            for k, v in sorted(obj.items())
            if v is not None
        }
    if isinstance(obj, (list, tuple)):
        return [_normalize(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        return _norm_number(obj)
    return obj


def canonical_json(config: Dict[str, Any]) -> str:
    """Compact, key-sorted, deterministic JSON for hashing."""
    return json.dumps(_normalize(config), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_config_hash(config: Dict[str, Any]) -> tuple[str, str]:
    """Return (short display hash, full SHA-256 hex) of the canonical config."""
    full = hashlib.sha256(canonical_json(config).encode("utf-8")).hexdigest()
    return full[:SHORT_HASH_LEN], full


# ---------------------------------------------------------------------------
# Per-engine normalizers (resolution-equivalent forms)
# ---------------------------------------------------------------------------


def _canon_cost(effective_cost_bps: float) -> Dict[str, Any]:
    # The engine's behaviour is fully determined by the effective per-side bps,
    # so the legacy field, simple_bps, and equivalent presets hash identically.
    return {"effective_cost_bps": _norm_number(round(float(effective_cost_bps), 6))}


def _canon_sizing(sizing: Optional[PositionSizing]) -> Dict[str, Any]:
    if sizing is None or sizing.type in ("full", "full_allocation"):
        return {"type": "full_allocation"}
    if sizing.type == "fixed_fraction":
        return {"type": "fixed_fraction", "fraction": sizing.fraction}
    if sizing.type == "max_exposure":
        return {"type": "max_exposure", "max_exposure": sizing.max_exposure}
    # volatility_target — engine defaults: lookback 20, cap 1.0
    return {
        "type": "volatility_target",
        "target_volatility": sizing.target_volatility,
        "lookback_days": sizing.lookback_days if sizing.lookback_days is not None else 20,
        "max_exposure": sizing.max_exposure if sizing.max_exposure is not None else 1.0,
    }


def _canon_risk(risk: Optional[RiskManagement]) -> Dict[str, Any]:
    if risk is None or risk.type == "none":
        return {"type": "none"}
    out: Dict[str, Any] = {"type": risk.type}
    if risk.type in ("fixed_stop_take_profit", "combined"):
        out["stop_loss_pct"] = risk.stop_loss_pct
        out["take_profit_pct"] = risk.take_profit_pct
    if risk.type in ("trailing_stop", "combined"):
        out["trailing_stop_pct"] = risk.trailing_stop_pct
    if risk.type in ("max_holding_days", "combined"):
        out["max_holding_days"] = risk.max_holding_days
    return out


def _canon_benchmark(benchmark: Optional[BenchmarkConfig]) -> Dict[str, Any]:
    if benchmark is None or benchmark.mode == "buy_and_hold_same_asset":
        return {"mode": "buy_and_hold_same_asset"}
    if benchmark.mode == "none":
        return {"mode": "none"}
    return {"mode": "custom_ticker", "ticker": (benchmark.ticker or "").upper()}


# ---------------------------------------------------------------------------
# Canonical configs
# ---------------------------------------------------------------------------


def normalize_backtest_config(
    *,
    strategy: str,
    ticker: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    strategy_params: Dict[str, Any],
    effective_cost_bps: float,
    position_sizing: Optional[PositionSizing],
    risk_management: Optional[RiskManagement],
    annualization_mode_used: str,
    benchmark: Optional[BenchmarkConfig],
    position_mode: str,
    data_provider: str,
    dataset_fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """Canonical config for a single-asset backtest (result-changing inputs only)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "strategy": strategy,
        "ticker": ticker.strip().upper(),
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": _norm_number(float(initial_capital)),
        "strategy_params": strategy_params,
        "cost_model": _canon_cost(effective_cost_bps),
        "position_sizing": _canon_sizing(position_sizing),
        "risk_management": _canon_risk(risk_management),
        "annualization_mode": annualization_mode_used,
        "benchmark": _canon_benchmark(benchmark),
        "position_mode": position_mode,
        "data_provider": data_provider,
        "dataset_fingerprint": dataset_fingerprint,
    }


def normalize_comparison_config(
    *,
    ticker: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    effective_cost_bps: float,
    position_sizing: Optional[PositionSizing],
    risk_management: Optional[RiskManagement],
    annualization_mode_used: str,
    benchmark: Optional[BenchmarkConfig],
    position_mode: str,
    strategies: list[str],
) -> Dict[str, Any]:
    """Canonical config for a Strategy Comparison run (shared settings)."""
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "ticker": ticker.strip().upper(),
        "start_date": start_date,
        "end_date": end_date,
        "initial_capital": _norm_number(float(initial_capital)),
        "strategies": sorted(strategies),
        "cost_model": _canon_cost(effective_cost_bps),
        "position_sizing": _canon_sizing(position_sizing),
        "risk_management": _canon_risk(risk_management),
        "annualization_mode": annualization_mode_used,
        "benchmark": _canon_benchmark(benchmark),
        "position_mode": position_mode,
        "data_provider": "yfinance",
    }


def build_reproducibility(config: Dict[str, Any]) -> Reproducibility:
    """Hash a canonical config into the response metadata block."""
    cj = canonical_json(config)
    full = hashlib.sha256(cj.encode("utf-8")).hexdigest()
    return Reproducibility(
        schema_version=str(config.get("schema_version", SCHEMA_VERSION)),
        config_hash=full[:SHORT_HASH_LEN],
        config_hash_full=full,
        canonical_config_json=cj,
    )
