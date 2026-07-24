"""
Portfolio-universe model (v1).

One universe = one shared, strictly increasing, tz-consistent timeline with
an identically aligned return matrix (assets × observations), a declared
return frequency, optional benchmark returns (kept separate — never mixed
into the asset matrix), optional prior weights, and per-asset metadata.
Strict identical alignment only: no forward fill, no fabricated
timestamps, no currency conversion, no expressions.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

MIN_ASSETS = 2
MAX_ASSETS = 20
MIN_OBSERVATIONS = 24
MAX_OBSERVATIONS = 2000
MAX_GROUPS = 8
MAX_ID_LENGTH = 64
ASSET_TYPES = ("equity", "futures", "crypto", "fx", "rates", "candidate",
               "index", "other")


class PortfolioInputError(ValueError):
    """Raised when supplied universe inputs violate the contract."""


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PortfolioInputError(f"{field} must be a finite number")
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise PortfolioInputError(f"{field} must be a finite number")
    if not math.isfinite(f):
        raise PortfolioInputError(f"{field} must be a finite number")
    return f


def _identifier(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PortfolioInputError(f"{field} must be a non-empty string")
    out = value.strip()
    if len(out) > MAX_ID_LENGTH:
        raise PortfolioInputError(f"{field} must be at most {MAX_ID_LENGTH} characters")
    return out


def normalize_timeline(raw: Any, frequency: Any) -> Dict[str, Any]:
    if not isinstance(frequency, str) or not frequency.strip():
        raise PortfolioInputError("frequency must be a non-empty string")
    if not isinstance(raw, list):
        raise PortfolioInputError("timestamps must be a list")
    if not (MIN_OBSERVATIONS <= len(raw) <= MAX_OBSERVATIONS):
        raise PortfolioInputError(
            f"timestamps must contain between {MIN_OBSERVATIONS} and "
            f"{MAX_OBSERVATIONS} entries")
    parsed: List[datetime] = []
    clean: List[str] = []
    for i, s in enumerate(raw):
        if not isinstance(s, str) or not s.strip():
            raise PortfolioInputError(f"timestamps[{i}] must be an ISO-8601 string")
        text = s.strip()
        try:
            parsed.append(datetime.fromisoformat(text))
        except ValueError:
            raise PortfolioInputError(
                f"timestamps[{i}] is not a valid ISO-8601 timestamp")
        clean.append(text)
    has_tz = parsed[0].tzinfo is not None
    if any((p.tzinfo is not None) != has_tz for p in parsed):
        raise PortfolioInputError(
            "timestamps mix timezone-aware and naive values")
    if any(parsed[i] >= parsed[i + 1] for i in range(len(parsed) - 1)):
        raise PortfolioInputError(
            "timestamps must be strictly increasing in time (no fabricated "
            "or duplicated timestamps)")
    return {"timestamps": clean, "frequency": frequency.strip()}


def normalize_assets(raw: Any, n_periods: int) -> List[Dict[str, Any]]:
    """Validate assets and keep the SUPPLIED order as canonical.

    The supplied order is the deterministic canonical ordering — it is
    fingerprinted, and every weight/covariance array preserves it.
    """
    if not isinstance(raw, list):
        raise PortfolioInputError("assets must be a list")
    if not (MIN_ASSETS <= len(raw) <= MAX_ASSETS):
        raise PortfolioInputError(
            f"assets must contain between {MIN_ASSETS} and {MAX_ASSETS} entries")
    out: List[Dict[str, Any]] = []
    ids = set()
    currencies = set()
    groups = set()
    for i, a in enumerate(raw):
        if not isinstance(a, dict):
            raise PortfolioInputError(f"assets[{i}] must be an object")
        asset_id = _identifier(a.get("asset_id"), f"assets[{i}].asset_id")
        if asset_id in ids:
            raise PortfolioInputError(f"duplicate asset_id {asset_id!r}")
        ids.add(asset_id)
        ref = f"asset {asset_id}"
        asset_type = a.get("asset_type", "other")
        if asset_type not in ASSET_TYPES:
            raise PortfolioInputError(
                f"{ref}: asset_type must be one of {', '.join(ASSET_TYPES)}")
        group = a.get("group")
        if group is not None:
            group = _identifier(group, f"{ref}: group")
            groups.add(group)
        currency = a.get("currency")
        if currency is not None:
            if not isinstance(currency, str) or not (1 <= len(currency.strip()) <= 8):
                raise PortfolioInputError(f"{ref}: currency must be a short string")
            currencies.add(currency.strip().upper())
        name = a.get("name")
        if name is not None and not isinstance(name, str):
            raise PortfolioInputError(f"{ref}: name must be a string")
        integer_lots = a.get("integer_lots", False)
        if not isinstance(integer_lots, bool):
            raise PortfolioInputError(f"{ref}: integer_lots must be a boolean")
        returns = a.get("returns")
        if not isinstance(returns, list) or len(returns) != n_periods:
            raise PortfolioInputError(
                f"{ref}: returns must align identically with the shared "
                f"timeline ({n_periods} observations); no forward fill")
        values = [_finite(v, f"{ref}: returns[{j}]") for j, v in enumerate(returns)]
        out.append({
            "asset_id": asset_id,
            "name": (name or asset_id)[:200],
            "asset_type": asset_type,
            "group": group,
            "currency": currency.strip().upper() if currency else None,
            "integer_lots": integer_lots,
            "returns": values,
        })
    if len(currencies) > 1:
        raise PortfolioInputError(
            "assets declare mixed currencies; v1 supports one currency per "
            "universe (no silent conversion)")
    if len(groups) > MAX_GROUPS:
        raise PortfolioInputError(f"at most {MAX_GROUPS} groups are supported")
    return out


def normalize_benchmark(raw: Any, n_periods: int) -> Optional[List[float]]:
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != n_periods:
        raise PortfolioInputError(
            "benchmark_returns must align identically with the shared "
            "timeline (it is never mixed into the asset matrix)")
    return [_finite(v, f"benchmark_returns[{j}]") for j, v in enumerate(raw)]


def normalize_prior_weights(raw: Any,
                            assets: List[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """Validate the prior book.  Assets absent from the supplied map are
    filled with 0.0 — the documented "not held in the prior book"
    convention (a position you do not hold IS zero; this is not a
    missing-data fabrication)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise PortfolioInputError("prior_weights must be an object")
    known = {a["asset_id"] for a in assets}
    out: Dict[str, float] = {}
    for key, value in raw.items():
        if key not in known:
            raise PortfolioInputError(
                f"prior_weights references unknown asset {key!r}")
        out[key] = _finite(value, f"prior_weights[{key}]")
    return {a["asset_id"]: out.get(a["asset_id"], 0.0) for a in assets}
