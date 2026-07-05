"""
Alternative Data, News Sentiment & Signal Decay Lab analytics (Phase 30.0) —
pure, deterministic.

Weighted sentiment scoring (sentiment × intensity × relevance × reliability),
novelty adjustment, exponential freshness decay on publication lag, a leakage
guard on feature-availability timestamps, event-study horizons, information
coefficient and hit rate, a signal-decay curve with a half-life estimate, a
composite alpha score, a deterministic research risk-regime classification, and
ten scenario stresses.

All outputs are finite by construction (correlations are null with a note on
zero variance; every division is guarded), so no NaN/Infinity reaches the API.
Educational only — not investment, trading, or signal advice; not a production
alpha engine; never live news, social media, market data, scraping, LLM APIs, or
paid data providers.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.alternative_data.models import (
    AltDataScenarioResult,
    AlternativeDataAnalysisRequest,
    AlternativeDataAnalysisResponse,
    AlternativeDataEventRow,
    EventStudyPoint,
    FreshnessAnalysis,
    LeakageGuard,
    RiskRegime,
    SampleSummary,
    SentimentAnalysis,
    SignalDecayPoint,
    SignalQuality,
)
from app.alternative_data.sample import DISCLAIMER

_EPS = 1e-12
_NEUTRAL_BAND = 0.1     # |sentiment| ≤ band → neutral event
_STALE_FRESHNESS = 0.5  # freshness below this → stale event
_SNR_CAP = 99.0

# Regime thresholds (deterministic, educational).
_RELIABILITY_LOW = 0.5
_IC_NOISY = 0.10
_HIT_NOISY = 0.5
_CROWDING_HIGH = 0.8
_SEVERE_TRIGGERS = 3

_HORIZONS = (1.0, 5.0, 20.0)

# id, name, description, sentiment_shift, intensity_mult, novelty_mult,
# reliability_mult, lag_mult, noise_amp, force_positive, leakage_injection
_SCENARIOS = [
    ("base", "Base case", "No shocks — the sample events as provided.", 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, False, 0),
    ("positive_news_burst", "Positive news burst", "Sentiment shifts +0.4 across events.", 0.4, 1.0, 1.0, 1.0, 1.0, 0.0, False, 0),
    ("negative_news_shock", "Negative news shock", "Sentiment shifts −0.4 across events.", -0.4, 1.0, 1.0, 1.0, 1.0, 0.0, False, 0),
    ("social_noise_spike", "Social sentiment noise spike", "Reliability sags while returns get noisier.", 0.0, 1.2, 1.0, 0.6, 1.0, 1.0, False, 0),
    ("reliability_downgrade", "Source reliability downgrade", "Source reliability halves.", 0.0, 1.0, 1.0, 0.5, 1.0, 0.0, False, 0),
    ("publication_lag_increase", "Publication lag increase", "Publication lags stretch ×8; freshness fades.", 0.0, 1.0, 1.0, 1.0, 8.0, 0.0, False, 0),
    ("novelty_collapse", "Novelty collapse", "Novelty scores collapse to 10%.", 0.0, 1.0, 0.1, 1.0, 1.0, 0.0, False, 0),
    ("crowded_event_cluster", "Crowded event cluster", "All events line up in the same direction.", 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, True, 0),
    ("leakage_violation", "Leakage violation sample", "Two features are stamped before their events (synthetic).", 0.0, 1.0, 1.0, 1.0, 1.0, 0.0, False, 2),
    ("severe_combo", "Severe alternative-data stress combo", "Reliability ×0.5, lags ×20, one leaked feature, noisier returns.", 0.0, 1.0, 1.0, 0.5, 20.0, 1.0, False, 1),
]


# --------------------------------------------------------------------------- #
# Small numeric helpers
# --------------------------------------------------------------------------- #
def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _corr(xs: List[float], ys: List[float]) -> Optional[float]:
    """Pearson correlation; None when either series has ~zero variance."""
    n = len(xs)
    if n < 2 or n != len(ys):
        return None
    mx, my = _mean(xs), _mean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx <= _EPS or sy <= _EPS:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return max(-1.0, min(cov / (sx * sy), 1.0))


def _hit_rate(xs: List[float], ys: List[float]) -> float:
    """Share of events where sign(signal) == sign(return); zeros count as misses."""
    if not xs:
        return 0.0
    hits = sum(1 for x, y in zip(xs, ys) if (x > 0 and y > 0) or (x < 0 and y < 0))
    return hits / len(xs)


def _freshness(lag_minutes: float, gamma_per_hour: float) -> float:
    exponent = max(min(gamma_per_hour * lag_minutes / 60.0, 50.0), 0.0)
    return math.exp(-exponent)


# --------------------------------------------------------------------------- #
# Event pipeline (dict-based so scenarios can transform copies)
# --------------------------------------------------------------------------- #
def _pipeline(
    events: List[Dict[str, float]], lam: float, gamma: float,
) -> List[Dict[str, float]]:
    out = []
    for e in events:
        weighted = e["s"] * e["intensity"] * e["relevance"] * e["reliability"]
        novelty_signal = weighted * (1.0 + lam * e["novelty"])
        fresh = _freshness(e["lag"], gamma)
        out.append({
            **e,
            "weighted": weighted,
            "novelty_signal": novelty_signal,
            "freshness": fresh,
            "signal": novelty_signal * fresh,
        })
    return out


def _events_to_dicts(req: AlternativeDataAnalysisRequest) -> List[Dict[str, float]]:
    return [
        {
            "s": e.sentiment_score,
            "intensity": e.event_intensity,
            "novelty": e.novelty_score,
            "reliability": e.source_reliability,
            "relevance": e.relevance_score,
            "lag": e.publication_lag_minutes,
            "r1": e.observed_return_1d,
            "r5": e.observed_return_5d,
            "r20": e.observed_return_20d,
            "leak": 1.0 if e.feature_available_timestamp < e.timestamp else 0.0,
        }
        for e in req.events
    ]


def _metrics(rows: List[Dict[str, float]]) -> Dict[str, object]:
    xs = [r["signal"] for r in rows]
    ic = {h: _corr(xs, [r[f"r{int(h)}"] for r in rows]) for h in _HORIZONS}
    hit = {h: _hit_rate(xs, [r[f"r{int(h)}"] for r in rows]) for h in _HORIZONS}
    leak_count = sum(1 for r in rows if r["leak"] > 0.5)
    pos = sum(1 for r in rows if r["s"] > _NEUTRAL_BAND)
    neg = sum(1 for r in rows if r["s"] < -_NEUTRAL_BAND)
    return {
        "avg_sentiment": _mean([r["s"] for r in rows]),
        "avg_intensity": _mean([r["intensity"] for r in rows]),
        "avg_novelty": _mean([r["novelty"] for r in rows]),
        "avg_reliability": _mean([r["reliability"] for r in rows]),
        "avg_freshness": _mean([r["freshness"] for r in rows]),
        "avg_weighted": _mean([r["weighted"] for r in rows]),
        "avg_lag": _mean([r["lag"] for r in rows]),
        "alpha": _mean(xs),
        "avg_signal": _mean(xs),
        "signal_std": _std(xs),
        "ic": ic,
        "hit": hit,
        "leak_count": leak_count,
        "pos": pos,
        "neg": neg,
        "neutral": len(rows) - pos - neg,
        "stale": sum(1 for r in rows if r["freshness"] < _STALE_FRESHNESS),
        "crowding": max(pos, neg) / len(rows) if rows else 0.0,
        "n": len(rows),
    }


# --------------------------------------------------------------------------- #
# Risk regime
# --------------------------------------------------------------------------- #
_REGIME_LABELS = {
    "clean_positive_signal": "Clean positive signal",
    "clean_negative_signal": "Clean negative signal",
    "noisy_signal": "Noisy signal",
    "stale_signal": "Stale signal",
    "leakage_risk": "Leakage risk",
    "low_reliability_signal": "Low-reliability signal",
    "crowded_event_risk": "Crowded event risk",
    "severe_altdata_stress": "Severe alt-data stress",
}

_REGIME_EXPLANATIONS = {
    "clean_positive_signal": "A net-positive signal that aligns with forward returns and passes the leakage guard in this sample.",
    "clean_negative_signal": "A net-negative signal that aligns with forward returns and passes the leakage guard in this sample.",
    "noisy_signal": "The signal shows little correlation with forward returns in this sample.",
    "stale_signal": "Publication lags leave the average feature stale by arrival in this sample.",
    "leakage_risk": "At least one feature is stamped before its event — a look-ahead leak in this sample.",
    "low_reliability_signal": "The average source reliability is low in this sample.",
    "crowded_event_risk": "Most events point the same direction — a crowded, one-sided event cluster in this sample.",
    "severe_altdata_stress": "Several data-quality dimensions are stressed at once in this sample.",
}


def _triggers(m: Dict[str, object]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    ic5 = m["ic"][5.0]  # type: ignore[index]
    if m["leak_count"] > 0:  # type: ignore[operator]
        out.append(("leakage_risk", f"{m['leak_count']} feature(s) stamped before their events"))
    if m["avg_freshness"] < _STALE_FRESHNESS:  # type: ignore[operator]
        out.append(("stale_signal", f"average freshness {m['avg_freshness']:.2f} < {_STALE_FRESHNESS:.1f}"))  # type: ignore[str-format]
    if m["avg_reliability"] < _RELIABILITY_LOW:  # type: ignore[operator]
        out.append(("low_reliability_signal", f"average source reliability {m['avg_reliability']:.2f} < {_RELIABILITY_LOW:.1f}"))  # type: ignore[str-format]
    if m["crowding"] >= _CROWDING_HIGH:  # type: ignore[operator]
        out.append(("crowded_event_risk", f"{m['crowding'] * 100:.0f}% of events point the same direction"))  # type: ignore[operator]
    if (ic5 is None or abs(ic5) < _IC_NOISY) or m["hit"][5.0] < _HIT_NOISY:  # type: ignore[index,operator]
        ic_txt = "n/a" if ic5 is None else f"{ic5:.2f}"
        out.append(("noisy_signal", f"IC(5d) {ic_txt} weak and/or hit rate {m['hit'][5.0] * 100:.0f}% low"))  # type: ignore[index,operator]
    return out


def _classify(m: Dict[str, object]) -> Tuple[str, str, List[str], str]:
    trig = _triggers(m)
    if len(trig) >= _SEVERE_TRIGGERS:
        rid = "severe_altdata_stress"
        return rid, _REGIME_LABELS[rid], [d for _, d in trig], _REGIME_EXPLANATIONS[rid]
    if trig:
        rid, driver = trig[0]  # priority = trigger order above
        return rid, _REGIME_LABELS[rid], [driver], _REGIME_EXPLANATIONS[rid]
    ic5 = m["ic"][5.0]  # type: ignore[index]
    rid = "clean_positive_signal" if m["alpha"] >= 0 else "clean_negative_signal"  # type: ignore[operator]
    drivers = [
        f"alpha score {m['alpha']:+.4f}",  # type: ignore[str-format]
        f"IC(5d) {ic5:.2f}" if ic5 is not None else "IC(5d) n/a",
        "no leakage flags",
    ]
    return rid, _REGIME_LABELS[rid], drivers, _REGIME_EXPLANATIONS[rid]


def _regime_score(m: Dict[str, object]) -> float:
    ic5 = m["ic"][5.0]  # type: ignore[index]
    ic_comp = 1.0 - min(abs(ic5) / 0.3, 1.0) if ic5 is not None else 1.0
    score = (
        0.25 * (1.0 if m["leak_count"] > 0 else 0.0)  # type: ignore[operator]
        + 0.20 * (1.0 - m["avg_freshness"])  # type: ignore[operator]
        + 0.20 * (1.0 - m["avg_reliability"])  # type: ignore[operator]
        + 0.20 * ic_comp
        + 0.15 * m["crowding"]  # type: ignore[operator]
    )
    return max(0.0, min(score, 1.0))


def _half_life(decay: Dict[float, Optional[float]]) -> Optional[float]:
    """Linear-interpolated horizon where |decay| first falls to half of |decay(1d)|."""
    d1 = decay.get(1.0)
    if d1 is None or abs(d1) <= _EPS:
        return None
    target = 0.5 * abs(d1)
    prev_h, prev_v = 1.0, abs(d1)
    for h in (5.0, 20.0):
        v = decay.get(h)
        if v is None:
            return None
        av = abs(v)
        if av <= target:
            if prev_v - av <= _EPS:
                return h
            return prev_h + (prev_v - target) / (prev_v - av) * (h - prev_h)
        prev_h, prev_v = h, av
    return None


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def analyze_alternative_data(req: AlternativeDataAnalysisRequest) -> AlternativeDataAnalysisResponse:
    lam = req.lambda_novelty
    gamma = req.gamma_freshness_per_hour
    rows = _pipeline(_events_to_dicts(req), lam, gamma)
    m = _metrics(rows)

    event_table = [
        AlternativeDataEventRow(
            event_id=e.event_id,
            timestamp=e.timestamp,
            symbol=e.symbol,
            source_type=e.source_type,
            headline=e.headline,
            sentiment_score=e.sentiment_score,
            event_intensity=e.event_intensity,
            novelty_score=e.novelty_score,
            source_reliability=e.source_reliability,
            relevance_score=e.relevance_score,
            weighted_sentiment=r["weighted"],
            novelty_adjusted_signal=r["novelty_signal"],
            freshness=r["freshness"],
            lag_adjusted_signal=r["signal"],
            observed_return_1d=e.observed_return_1d,
            observed_return_5d=e.observed_return_5d,
            observed_return_20d=e.observed_return_20d,
            leakage_flag=r["leak"] > 0.5,
        )
        for e, r in zip(req.events, rows)
    ]

    sentiment = SentimentAnalysis(
        average_sentiment=m["avg_sentiment"],
        weighted_sentiment_average=m["avg_weighted"],
        positive_event_count=m["pos"],
        negative_event_count=m["neg"],
        neutral_event_count=m["neutral"],
        alpha_score=m["alpha"],
    )

    freshness = FreshnessAnalysis(
        average_publication_lag_minutes=m["avg_lag"],
        average_freshness=m["avg_freshness"],
        stale_event_count=m["stale"],
        notes=[
            f"Freshness = exp(−γ·lag) with γ = {gamma:g} per hour; events below "
            f"{_STALE_FRESHNESS:.1f} freshness count as stale.",
        ],
    )

    leakage = LeakageGuard(
        leakage_count=m["leak_count"],
        leakage_rate=m["leak_count"] / m["n"] if m["n"] else 0.0,
        has_leakage=m["leak_count"] > 0,
        notes=[
            "A feature stamped before its event timestamp is a look-ahead leak; "
            "valid samples carry zero leakage flags (input validation enforces the "
            "ordering, so leaks here only appear in the synthetic leakage scenario).",
        ],
    )

    ic5 = m["ic"][5.0]
    snr = min(abs(m["avg_signal"]) / m["signal_std"], _SNR_CAP) if m["signal_std"] > _EPS else 0.0
    quality_notes = ["Reliability-weighted quality = average reliability × |IC(5d)|."]
    if any(v is None for v in m["ic"].values()):
        quality_notes.append("An IC shown as null means the signal or return series had zero variance.")
    signal_quality = SignalQuality(
        information_coefficient_1d=m["ic"][1.0],
        information_coefficient_5d=ic5,
        information_coefficient_20d=m["ic"][20.0],
        hit_rate_1d=m["hit"][1.0],
        hit_rate_5d=m["hit"][5.0],
        hit_rate_20d=m["hit"][20.0],
        signal_to_noise_score=snr,
        reliability_weighted_quality=m["avg_reliability"] * (abs(ic5) if ic5 is not None else 0.0),
        notes=quality_notes,
    )

    event_study = [
        EventStudyPoint(
            horizon_days=h,
            average_forward_return=_mean([r[f"r{int(h)}"] for r in rows]),
            average_signal=m["avg_signal"],
            ic_at_horizon=m["ic"][h],
        )
        for h in _HORIZONS
    ]

    half_life = _half_life(m["ic"])
    signal_decay = [
        SignalDecayPoint(
            horizon_days=h,
            decay_correlation=m["ic"][h],
            signal_half_life_estimate=half_life if h == 1.0 else None,
        )
        for h in _HORIZONS
    ]

    rid, label, drivers, explanation = _classify(m)
    regime = RiskRegime(
        regime_id=rid,
        regime_label=label,
        score=_regime_score(m),
        drivers=drivers,
        explanation=explanation,
    )

    scenarios = _scenarios(req, lam, gamma)

    return AlternativeDataAnalysisResponse(
        sample_summary=SampleSummary(
            sample_id=req.sample_id,
            sample_name=req.sample_name,
            event_count=len(req.events),
            symbols=sorted({e.symbol for e in req.events}),
            source_types=sorted({e.source_type for e in req.events}),
        ),
        event_table=event_table,
        sentiment_analysis=sentiment,
        freshness_analysis=freshness,
        leakage_guard=leakage,
        signal_quality=signal_quality,
        event_study=event_study,
        signal_decay=signal_decay,
        risk_regime=regime,
        scenario_results=scenarios,
        notes=[
            "Signal pipeline: weighted sentiment s·I·R·Q → novelty adjustment "
            "×(1+λN) → freshness decay ×exp(−γ·lag) → lag-adjusted signal; alpha "
            "score is the plain average of lag-adjusted signals.",
            "IC is the Pearson correlation of the lag-adjusted signal with the "
            "observed forward return at each horizon; the decay curve is the same "
            "correlation across horizons.",
            "Observed returns are hand-written sample paths — not market data; the "
            "sample is designed to illustrate the workflow, not evidence of alpha.",
            "Regime classification and stress scenarios are deterministic educational "
            "examples on static sample data — not forecasts, signals, or advice.",
        ],
        disclaimer=DISCLAIMER,
    )


def _scenarios(
    req: AlternativeDataAnalysisRequest, lam: float, gamma: float,
) -> List[AltDataScenarioResult]:
    base_events = _events_to_dicts(req)
    results: List[AltDataScenarioResult] = []

    for sid, name, desc, s_shift, i_mult, n_mult, q_mult, lag_mult, noise_amp, force_pos, leak_n in _SCENARIOS:
        events: List[Dict[str, float]] = []
        for idx, e in enumerate(base_events):
            s = max(-1.0, min(e["s"] + s_shift, 1.0))
            if force_pos:
                s = abs(s)
            noise = noise_amp * 0.02 * (1.0 if idx % 2 == 0 else -1.0)
            events.append({
                **e,
                "s": s,
                "intensity": max(0.0, min(e["intensity"] * i_mult, 1.0)),
                "novelty": max(0.0, min(e["novelty"] * n_mult, 1.0)),
                "reliability": max(0.0, min(e["reliability"] * q_mult, 1.0)),
                "lag": e["lag"] * lag_mult,
                "r1": e["r1"] + noise,
                "r5": e["r5"] + noise,
                "r20": e["r20"] + noise,
                "leak": 1.0 if idx < leak_n else e["leak"],
            })
        rows = _pipeline(events, lam, gamma)
        m = _metrics(rows)
        _, regime_label, _, _ = _classify(m)

        results.append(
            AltDataScenarioResult(
                id=sid,
                name=name,
                description=desc,
                average_sentiment=m["avg_sentiment"],
                average_intensity=m["avg_intensity"],
                average_novelty=m["avg_novelty"],
                average_reliability=m["avg_reliability"],
                average_freshness=m["avg_freshness"],
                alpha_score=m["alpha"],
                information_coefficient_5d=m["ic"][5.0],
                hit_rate_5d=m["hit"][5.0],
                leakage_count=m["leak_count"],
                decay_5d=m["ic"][5.0],
                decay_20d=m["ic"][20.0],
                regime_label=regime_label,
                notes=["Illustrative deterministic scenario — not a forecast or advice."],
            )
        )
    return results
