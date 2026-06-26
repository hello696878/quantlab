"""
Order Flow Toxicity & Liquidity Metrics analytics (Phase 25.2) — pure, deterministic.

Educational order-flow toxicity and liquidity diagnostics computed from a
deterministic signed trade tape and quote sequence: order-flow imbalance (OFI),
queue imbalance (QI), effective / realized spread, adverse-selection cost, a
simplified VPIN-style toxicity metric, a Kyle-lambda approximation, an Amihud
illiquidity approximation, a liquidity-regime classification, and eight toxic-flow
stress scenarios.

All outputs are finite by construction (every division is guarded; Kyle lambda is
null with a note when signed-volume variance is zero), so no NaN/Infinity reaches
the API. Static illustrative sample data — educational only, not investment,
trading, order-routing, legal, tax, or risk-management advice; the VPIN-style
metric is a simplified educational approximation, not exchange VPIN.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.microstructure.models import (
    LiquidityRegime,
    MarketMicrostructureAnalysisRequest,
    OrderFlowSummary,
    OrderFlowToxicityResult,
    SpreadQuality,
    ToxicityMetrics,
    ToxicityScenarioResult,
)

_EPS = 1e-12

TOXICITY_DISCLAIMER = (
    "Static illustrative sample data. Order-flow toxicity and liquidity analytics "
    "are educational and not investment, trading, order-routing, legal, tax, or "
    "risk-management advice."
)

# Default config used when a request omits `toxicity_config`.
_DEFAULT_CONFIG = {
    "realized_spread_horizon_seconds": 30.0,
    "vpin_window_buckets": 10,
    "lambda_window_trades": 50,
    "regime_threshold_low": 0.2,
    "regime_threshold_high": 0.4,
}

# Regime references (bps) for the deterministic classifier.
_SPREAD_HIGH_BPS = 6.0
_ADVERSE_HIGH_BPS = 1.5
_ADVERSE_VERY_HIGH_BPS = 3.5
_ADVERSE_LOW_BPS = 0.4
_OFI_STRONG = 0.35

# id, name, description, trade-transform kwargs, quote size mult, quote imbalance amp
_TOX_SCENARIOS = [
    ("base", "Base case", "No shocks — the sample flow as provided.", {}, 1.0, 1.0),
    ("buy_pressure_wave", "Buy pressure wave", "Buy-initiated volume surges; order-flow imbalance rises.", {"buy_m": 1.8, "sell_m": 0.5}, 1.0, 1.0),
    ("sell_pressure_wave", "Sell pressure wave", "Sell-initiated volume surges; order-flow imbalance falls.", {"buy_m": 0.5, "sell_m": 1.8}, 1.0, 1.0),
    ("spread_widening", "Spread widening", "Traded distance from mid widens; effective spread rises.", {"price_dev_m": 2.0}, 1.0, 1.0),
    ("depth_evaporation", "Depth evaporation", "Top-of-book size collapses and skews; queue imbalance sharpens.", {"size_m": 0.6}, 0.4, 2.0),
    ("toxic_informed_flow", "Toxic informed flow", "Permanent post-trade drift grows; adverse selection rises.", {"adverse_m": 2.2}, 1.0, 1.0),
    ("volume_drought", "Volume drought", "Trade sizes shrink sharply; Amihud illiquidity rises.", {"size_m": 0.3}, 1.0, 1.0),
    ("liquidity_recovery", "Liquidity recovery", "Spreads tighten and flow balances; the regime improves.", {"price_dev_m": 0.5, "adverse_m": 0.3, "buy_m": 0.85, "sell_m": 0.85}, 1.0, 1.0),
]


# --------------------------------------------------------------------------- #
# Normalisation (pydantic inputs → lightweight dicts)
# --------------------------------------------------------------------------- #
def _normalize_trades(signed_trades, horizon_seconds: float) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    short_horizon = horizon_seconds <= 5.0
    for t in signed_trades:
        eps = 1.0 if t.side == "buy" else -1.0
        if short_horizon and t.mid_after_5s is not None:
            m_after = float(t.mid_after_5s)
        elif t.mid_after_30s is not None:
            m_after = float(t.mid_after_30s)
        elif t.mid_after_5s is not None:
            m_after = float(t.mid_after_5s)
        else:
            m_after = float(t.mid_before)
        out.append({
            "eps": eps,
            "size": float(t.size),
            "price": float(t.price),
            "m_before": float(t.mid_before),
            "m_after": m_after,
        })
    return out


def _normalize_quotes(quotes) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for q in quotes:
        mid = float(q.mid_price) if q.mid_price is not None else (float(q.bid) + float(q.ask)) / 2.0
        out.append({
            "bid": float(q.bid),
            "ask": float(q.ask),
            "bid_size": float(q.bid_size),
            "ask_size": float(q.ask_size),
            "mid": mid,
        })
    return out


def _derive_trades_from_tape(req: MarketMicrostructureAnalysisRequest, mid: float, tick: float) -> List[Dict[str, float]]:
    """Fallback: derive a signed sequence from the plain trade tape + book mid."""
    a = 0.3 * (tick / 2.0)
    out: List[Dict[str, float]] = []
    for t in req.trades:
        eps = 1.0 if t.side == "buy" else -1.0
        out.append({
            "eps": eps,
            "size": float(t.size),
            "price": float(t.price),
            "m_before": mid,
            "m_after": mid + eps * a,
        })
    return out


def _derive_quotes_from_book(bids, asks) -> List[Dict[str, float]]:
    """Fallback: a single quote snapshot from the order-book top levels."""
    bid = bids[0].price
    ask = asks[0].price
    return [{
        "bid": bid,
        "ask": ask,
        "bid_size": bids[0].size,
        "ask_size": asks[0].size,
        "mid": (bid + ask) / 2.0,
    }]


# --------------------------------------------------------------------------- #
# Small numeric helpers
# --------------------------------------------------------------------------- #
def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _percentile(xs: List[float], p: float) -> float:
    if not xs:
        return 0.0
    ordered = sorted(xs)
    if len(ordered) == 1:
        return ordered[0]
    rank = (p / 100.0) * (len(ordered) - 1)
    lo = int(math.floor(rank))
    hi = int(math.ceil(rank))
    if lo == hi:
        return ordered[lo]
    frac = rank - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# --------------------------------------------------------------------------- #
# Core metrics
# --------------------------------------------------------------------------- #
def _vpin(trades: List[Dict[str, float]], bucket_volume: float, window: int) -> Tuple[float, int]:
    """Simplified VPIN-style metric over equal-volume buckets (trades split across buckets)."""
    if bucket_volume <= _EPS:
        return 0.0, 0
    buckets: List[Tuple[float, float]] = []
    cur_buy = cur_sell = cur_fill = 0.0
    for t in trades:
        remaining = t["size"]
        is_buy = t["eps"] > 0
        while remaining > _EPS:
            space = bucket_volume - cur_fill
            take = min(space, remaining)
            if is_buy:
                cur_buy += take
            else:
                cur_sell += take
            cur_fill += take
            remaining -= take
            if cur_fill >= bucket_volume - _EPS:
                buckets.append((cur_buy, cur_sell))
                cur_buy = cur_sell = cur_fill = 0.0
    if not buckets and (cur_buy + cur_sell) > _EPS:
        buckets.append((cur_buy, cur_sell))
    imbalances = [abs(b - s) / (b + s) for (b, s) in buckets if (b + s) > _EPS]
    used = imbalances[-window:] if (window and 0 < window < len(imbalances)) else imbalances
    vpin = _mean(used)
    return _clamp01(vpin), len(buckets)


def _kyle_lambda(trades: List[Dict[str, float]], window: int) -> Tuple[Optional[float], Optional[str]]:
    """Regression slope of mid-price change on signed volume; null if variance is zero."""
    pts = trades[-window:] if (window and 0 < window < len(trades)) else trades
    xs = [t["eps"] * t["size"] for t in pts]
    dps = [t["m_after"] - t["m_before"] for t in pts]
    n = len(xs)
    if n < 2:
        return None, "Not enough trades for a Kyle-lambda regression."
    mx = _mean(xs)
    mp = _mean(dps)
    var = sum((x - mx) ** 2 for x in xs) / n
    if var <= _EPS:
        return None, "Zero signed-volume variance — Kyle lambda is undefined here."
    cov = sum((x - mx) * (d - mp) for x, d in zip(xs, dps)) / n
    return cov / var, None


def _amihud(trades: List[Dict[str, float]]) -> float:
    vals: List[float] = []
    for t in trades:
        m = t["m_before"]
        dollar_volume = t["price"] * t["size"]
        if m > _EPS and dollar_volume > _EPS:
            r = abs((t["m_after"] - m) / m)
            vals.append(r / dollar_volume)
    return _mean(vals)


def _spread_series(trades: List[Dict[str, float]]) -> Tuple[List[float], List[float], List[float]]:
    eff: List[float] = []
    real: List[float] = []
    adv: List[float] = []
    for t in trades:
        m = t["m_before"]
        if m <= _EPS:
            continue
        e = 2.0 * t["eps"] * (t["price"] - m) / m * 10000.0
        r = 2.0 * t["eps"] * (t["price"] - t["m_after"]) / m * 10000.0
        eff.append(e)
        real.append(r)
        adv.append(e - r)
    return eff, real, adv


def _avg_queue_imbalance(quotes: List[Dict[str, float]]) -> float:
    qis = [
        (q["bid_size"] - q["ask_size"]) / (q["bid_size"] + q["ask_size"])
        for q in quotes
        if (q["bid_size"] + q["ask_size"]) > _EPS
    ]
    return _mean(qis)


def _core_metrics(trades: List[Dict[str, float]], quotes: List[Dict[str, float]], config: Dict) -> Dict:
    total_vol = sum(t["size"] for t in trades)
    buy_vol = sum(t["size"] for t in trades if t["eps"] > 0)
    sell_vol = sum(t["size"] for t in trades if t["eps"] < 0)
    signed_vol = sum(t["eps"] * t["size"] for t in trades)
    ofi = max(-1.0, min(1.0, signed_vol / total_vol)) if total_vol > _EPS else 0.0

    avg_qi = max(-1.0, min(1.0, _avg_queue_imbalance(quotes)))

    eff, real, adv = _spread_series(trades)
    avg_eff = _mean(eff)
    avg_real = _mean(real)
    avg_adv = _mean(adv)
    eff_p95 = _percentile(eff, 95.0)
    adv_p95 = _percentile(adv, 95.0)

    vpin, n_buckets = _vpin(trades, config["bucket_volume"], int(config["vpin_window_buckets"]))
    kyle, kyle_note = _kyle_lambda(trades, int(config["lambda_window_trades"]))
    amihud = _amihud(trades)

    adv_frac = _clamp01(avg_adv / avg_eff) if avg_eff > _EPS else 0.0
    toxicity_score = _clamp01(0.5 * vpin + 0.5 * adv_frac)

    return {
        "trade_count": len(trades),
        "buy_volume": buy_vol,
        "sell_volume": sell_vol,
        "total_volume": total_vol,
        "signed_volume": signed_vol,
        "ofi": ofi,
        "avg_qi": avg_qi,
        "avg_eff": avg_eff,
        "avg_real": avg_real,
        "avg_adv": avg_adv,
        "eff_p95": eff_p95,
        "adv_p95": adv_p95,
        "vpin": vpin,
        "vpin_buckets": n_buckets,
        "kyle": kyle,
        "kyle_note": kyle_note,
        "amihud": amihud,
        "toxicity_score": toxicity_score,
    }


# --------------------------------------------------------------------------- #
# Liquidity regime classification
# --------------------------------------------------------------------------- #
def _classify_regime(core: Dict, config: Dict) -> Tuple[str, str, List[str], str]:
    vpin = core["vpin"]
    eff = core["avg_eff"]
    adv = core["avg_adv"]
    ofi = core["ofi"]
    lo = config["regime_threshold_low"]
    hi = config["regime_threshold_high"]
    drivers: List[str] = []

    if (vpin >= hi and adv >= _ADVERSE_HIGH_BPS) or adv >= _ADVERSE_VERY_HIGH_BPS:
        if adv >= _ADVERSE_VERY_HIGH_BPS:
            drivers = [f"adverse selection {adv:.2f} bps ≥ {_ADVERSE_VERY_HIGH_BPS:.1f}"]
        else:
            drivers = [f"VPIN {vpin:.2f} ≥ {hi:.2f}", f"adverse selection {adv:.2f} bps ≥ {_ADVERSE_HIGH_BPS:.1f}"]
        return ("toxic_flow", "Toxic flow", drivers,
                "Elevated VPIN and/or adverse selection — flow looks informed/toxic in this sample.")
    if eff >= _SPREAD_HIGH_BPS:
        drivers = [f"effective spread {eff:.2f} bps ≥ {_SPREAD_HIGH_BPS:.1f}"]
        return ("stressed_illiquid", "Stressed / illiquid", drivers,
                "Wide effective spread — liquidity looks stressed in this sample.")
    if abs(ofi) >= _OFI_STRONG:
        drivers = [f"|OFI| {abs(ofi):.2f} ≥ {_OFI_STRONG:.2f}", f"effective spread {eff:.2f} bps < {_SPREAD_HIGH_BPS:.1f}"]
        side = "buy" if ofi > 0 else "sell"
        return ("one_sided_flow", "One-sided flow", drivers,
                f"Strong {side}-side order-flow imbalance with normal spreads — directional but not toxic.")
    if vpin <= lo and eff < _SPREAD_HIGH_BPS and adv < _ADVERSE_LOW_BPS:
        drivers = [f"VPIN {vpin:.2f} ≤ {lo:.2f}", f"effective spread {eff:.2f} bps", f"adverse selection {adv:.2f} bps < {_ADVERSE_LOW_BPS:.1f}"]
        return ("calm_liquid", "Calm / liquid", drivers,
                "Low VPIN, tight spreads, and low adverse selection — calm, liquid conditions in this sample.")
    drivers = [f"VPIN {vpin:.2f}", f"effective spread {eff:.2f} bps", f"OFI {ofi:.2f}"]
    return ("balanced", "Balanced", drivers,
            "Mixed signals — neither clearly calm nor clearly toxic in this sample.")


# --------------------------------------------------------------------------- #
# Scenario transforms
# --------------------------------------------------------------------------- #
def _transform_trades(
    trades: List[Dict[str, float]],
    buy_m: float = 1.0,
    sell_m: float = 1.0,
    price_dev_m: float = 1.0,
    adverse_m: float = 1.0,
    size_m: float = 1.0,
) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for t in trades:
        m = t["m_before"]
        side_m = buy_m if t["eps"] > 0 else sell_m
        size = max(t["size"] * size_m * side_m, 1e-9)
        price = max(m + (t["price"] - m) * price_dev_m, 1e-9)
        m_after = max(m + (t["m_after"] - m) * adverse_m, 1e-9)
        out.append({"eps": t["eps"], "size": size, "price": price, "m_before": m, "m_after": m_after})
    return out


def _transform_quotes(quotes: List[Dict[str, float]], size_m: float = 1.0, imb_amp: float = 1.0) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for q in quotes:
        b, a = q["bid_size"], q["ask_size"]
        mean = (b + a) / 2.0
        nb = max((mean + (b - mean) * imb_amp) * size_m, 1e-9)
        na = max((mean + (a - mean) * imb_amp) * size_m, 1e-9)
        out.append({"bid": q["bid"], "ask": q["ask"], "bid_size": nb, "ask_size": na, "mid": q["mid"]})
    return out


def _scenarios(
    base_trades: List[Dict[str, float]],
    base_quotes: List[Dict[str, float]],
    config: Dict,
) -> List[ToxicityScenarioResult]:
    results: List[ToxicityScenarioResult] = []
    for sid, name, desc, trade_kw, quote_size_m, quote_amp in _TOX_SCENARIOS:
        trades = _transform_trades(base_trades, **trade_kw) if trade_kw else list(base_trades)
        quotes = (
            _transform_quotes(base_quotes, size_m=quote_size_m, imb_amp=quote_amp)
            if (quote_size_m != 1.0 or quote_amp != 1.0)
            else list(base_quotes)
        )
        core = _core_metrics(trades, quotes, config)
        _, regime_label, _, _ = _classify_regime(core, config)
        results.append(
            ToxicityScenarioResult(
                id=sid,
                name=name,
                description=desc,
                order_flow_imbalance=core["ofi"],
                queue_imbalance=core["avg_qi"],
                vpin=core["vpin"],
                effective_spread_bps=core["avg_eff"],
                realized_spread_bps=core["avg_real"],
                adverse_selection_bps=core["avg_adv"],
                kyle_lambda=core["kyle"],
                amihud_illiquidity=core["amihud"],
                regime_label=regime_label,
                notes=["Illustrative deterministic scenario — not a forecast or advice."],
            )
        )
    return results


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_order_flow_toxicity(req: MarketMicrostructureAnalysisRequest) -> OrderFlowToxicityResult:
    book = req.order_book
    bids = sorted(book.bids, key=lambda x: x.price, reverse=True)
    asks = sorted(book.asks, key=lambda x: x.price)
    mid = (bids[0].price + asks[0].price) / 2.0
    tick = max(asks[0].price - bids[0].price, _EPS)

    # Resolve config (defaults + provided overrides).
    if req.toxicity_config is not None:
        cfg = req.toxicity_config
        config = {
            "bucket_volume": float(cfg.bucket_volume),
            "realized_spread_horizon_seconds": float(cfg.realized_spread_horizon_seconds),
            "vpin_window_buckets": int(cfg.vpin_window_buckets),
            "lambda_window_trades": int(cfg.lambda_window_trades),
            "regime_threshold_low": float(cfg.regime_threshold_low),
            "regime_threshold_high": float(cfg.regime_threshold_high),
        }
    else:
        config = dict(_DEFAULT_CONFIG)

    # Resolve trades / quotes (provided or derived).
    if req.signed_trades:
        trades = _normalize_trades(req.signed_trades, config["realized_spread_horizon_seconds"])
    else:
        trades = _derive_trades_from_tape(req, mid, tick)
    if req.quotes:
        quotes = _normalize_quotes(req.quotes)
    else:
        quotes = _derive_quotes_from_book(bids, asks)

    # Default bucket volume if none configured: ~12 equal-volume buckets.
    if "bucket_volume" not in config or config["bucket_volume"] <= _EPS:
        total = sum(t["size"] for t in trades)
        config["bucket_volume"] = max(total / 12.0, _EPS)

    core = _core_metrics(trades, quotes, config)
    regime_id, regime_label, drivers, explanation = _classify_regime(core, config)
    scenarios = _scenarios(trades, quotes, config)

    metric_notes = [
        "VPIN is a simplified educational VPIN-style metric over equal-volume buckets — not exchange VPIN.",
        "Kyle lambda is a regression slope of mid change on signed volume (null when variance is zero).",
        "Amihud illiquidity averages |return| / dollar-volume across trades.",
    ]

    return OrderFlowToxicityResult(
        order_flow_summary=OrderFlowSummary(
            trade_count=core["trade_count"],
            buy_volume=core["buy_volume"],
            sell_volume=core["sell_volume"],
            total_volume=core["total_volume"],
            signed_volume=core["signed_volume"],
            order_flow_imbalance=core["ofi"],
            average_queue_imbalance=core["avg_qi"],
        ),
        spread_quality=SpreadQuality(
            average_effective_spread_bps=core["avg_eff"],
            average_realized_spread_bps=core["avg_real"],
            average_adverse_selection_bps=core["avg_adv"],
            effective_spread_p95_bps=core["eff_p95"],
            adverse_selection_p95_bps=core["adv_p95"],
        ),
        toxicity_metrics=ToxicityMetrics(
            vpin=core["vpin"],
            vpin_bucket_count=core["vpin_buckets"],
            kyle_lambda=core["kyle"],
            amihud_illiquidity=core["amihud"],
            toxicity_score=core["toxicity_score"],
            notes=([core["kyle_note"]] if core["kyle_note"] else []) + metric_notes,
        ),
        liquidity_regime=LiquidityRegime(
            regime_id=regime_id,
            regime_label=regime_label,
            score=core["toxicity_score"],
            drivers=drivers,
            explanation=explanation,
        ),
        toxicity_scenarios=scenarios,
        formula_notes=[
            "OFI = Σεᵢqᵢ / Σqᵢ (bounded −1..1); QI = (Q_b − Q_a)/(Q_b + Q_a).",
            "Effective spread = 2εᵢ(pᵢ − mᵢ)/mᵢ·10⁴; realized = 2εᵢ(pᵢ − m_{i+h})/mᵢ·10⁴.",
            "Adverse selection = effective − realized; VPIN = mean bucket |buy−sell|/(buy+sell).",
            "Kyle λ ≈ Cov(Δp, x)/Var(x); Amihud = mean |r| / dollar-volume.",
        ],
        disclaimer=TOXICITY_DISCLAIMER,
    )
