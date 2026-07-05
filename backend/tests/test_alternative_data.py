"""
Tests for the Alternative Data, News Sentiment & Signal Decay Lab (Phase 30.0).

Confirms the static-sample API shape, validation, JSON-safety (no NaN/Inf), and
the analytics' mathematical correctness. Fully deterministic — no network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.alternative_data.models import AlternativeDataAnalysisRequest
from app.alternative_data.sample import sample_requests
from app.alternative_data.service import analyze_alternative_data

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _assert_all_finite(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj), f"non-finite float in payload: {obj}"


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _megacap():
    return sample_requests()[0]


def _analyze(req=None):
    return analyze_alternative_data(req or _megacap())


def _scenario(out, sid):
    return next(s for s in out.scenario_results if s.id == sid)


# --------------------------------------------------------------------------- #
# 1–2. Endpoints
# --------------------------------------------------------------------------- #
def test_sample_endpoint(client):
    res = client.get("/alternative-data/sample")
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    ids = {s["sample_id"] for s in body["samples"]}
    assert ids == {
        "MEGACAP_NEWS_SAMPLE", "CRYPTO_SENTIMENT_SAMPLE", "EARNINGS_SURPRISE_SAMPLE",
        "MACRO_SHOCK_SAMPLE", "SUPPLY_CHAIN_SAMPLE",
    }
    assert "not investment" in body["disclaimer"].lower()
    _assert_all_finite(body)


def test_analyze_endpoint(client):
    res = client.post("/alternative-data/analyze", json=_megacap().model_dump())
    assert res.status_code == 200
    body = res.json()
    assert body["data_status"] == "static_sample"
    assert "signal-quality" in body["disclaimer"].lower()
    _assert_all_finite(body)


# --------------------------------------------------------------------------- #
# 3–7. Signal pipeline formulas
# --------------------------------------------------------------------------- #
def test_weighted_sentiment_formula():
    req = _megacap()
    out = _analyze(req)
    e = req.events[0]
    row = out.event_table[0]
    expected = e.sentiment_score * e.event_intensity * e.relevance_score * e.source_reliability
    assert math.isclose(row.weighted_sentiment, expected, rel_tol=1e-12)


def test_novelty_adjusted_signal_formula():
    req = _megacap()
    out = _analyze(req)
    e = req.events[0]
    row = out.event_table[0]
    expected = row.weighted_sentiment * (1.0 + req.lambda_novelty * e.novelty_score)
    assert math.isclose(row.novelty_adjusted_signal, expected, rel_tol=1e-12)


def test_freshness_decay_formula_finite():
    req = _megacap()
    out = _analyze(req)
    for e, row in zip(req.events, out.event_table):
        expected = math.exp(-req.gamma_freshness_per_hour * e.publication_lag_minutes / 60.0)
        assert math.isfinite(row.freshness)
        assert math.isclose(row.freshness, expected, rel_tol=1e-12)
        assert 0.0 < row.freshness <= 1.0


def test_lag_adjusted_signal_formula():
    out = _analyze()
    for row in out.event_table:
        assert math.isclose(row.lag_adjusted_signal, row.novelty_adjusted_signal * row.freshness, rel_tol=1e-12)


def test_alpha_score_formula():
    out = _analyze()
    signals = [row.lag_adjusted_signal for row in out.event_table]
    assert math.isclose(out.sentiment_analysis.alpha_score, sum(signals) / len(signals), rel_tol=1e-12)


# --------------------------------------------------------------------------- #
# 8–10. IC / hit rate / decay
# --------------------------------------------------------------------------- #
def test_information_coefficient_finite_or_null():
    for req in sample_requests():
        sq = analyze_alternative_data(req).signal_quality
        for v in (sq.information_coefficient_1d, sq.information_coefficient_5d, sq.information_coefficient_20d):
            assert v is None or (math.isfinite(v) and -1.0 <= v <= 1.0)


def test_ic_null_on_zero_variance_with_note():
    base = _megacap().model_dump()
    for e in base["events"]:
        e["observed_return_5d"] = 0.01  # constant → zero variance
    req = AlternativeDataAnalysisRequest(**base)
    sq = analyze_alternative_data(req).signal_quality
    assert sq.information_coefficient_5d is None
    assert any("zero variance" in n for n in sq.notes)


def test_hit_rate_formula():
    out = _analyze()
    rows = out.event_table
    hits = sum(
        1 for r in rows
        if (r.lag_adjusted_signal > 0 and r.observed_return_5d > 0)
        or (r.lag_adjusted_signal < 0 and r.observed_return_5d < 0)
    )
    assert math.isclose(out.signal_quality.hit_rate_5d, hits / len(rows), rel_tol=1e-12)


def test_signal_decay_curve():
    out = _analyze()
    horizons = [p.horizon_days for p in out.signal_decay]
    assert horizons == [1.0, 5.0, 20.0]
    for p, es in zip(out.signal_decay, out.event_study):
        assert p.decay_correlation == es.ic_at_horizon
        if p.decay_correlation is not None:
            assert math.isfinite(p.decay_correlation)


# --------------------------------------------------------------------------- #
# 11–14. Leakage / counts / freshness
# --------------------------------------------------------------------------- #
def test_leakage_guard_clean_on_base_samples():
    for req in sample_requests():
        lg = analyze_alternative_data(req).leakage_guard
        assert lg.leakage_count == 0 and not lg.has_leakage and lg.leakage_rate == 0.0


def test_leakage_guard_detects_scenario_leakage():
    out = _analyze()
    leak = _scenario(out, "leakage_violation")
    assert leak.leakage_count == 2
    assert leak.regime_label == "Leakage risk"


def test_sentiment_event_counts():
    out = _analyze()  # megacap: 4 positive, 3 negative, 1 neutral (|s| ≤ 0.1)
    sa = out.sentiment_analysis
    assert sa.positive_event_count == 4
    assert sa.negative_event_count == 3
    assert sa.neutral_event_count == 1


def test_freshness_decreases_when_lag_increases():
    for req in sample_requests():
        out = analyze_alternative_data(req)
        base = _scenario(out, "base")
        assert _scenario(out, "publication_lag_increase").average_freshness < base.average_freshness


# --------------------------------------------------------------------------- #
# 15–19. Scenario intuitions & regimes
# --------------------------------------------------------------------------- #
def test_positive_burst_raises_alpha():
    for req in sample_requests():
        out = analyze_alternative_data(req)
        assert _scenario(out, "positive_news_burst").alpha_score > _scenario(out, "base").alpha_score


def test_negative_shock_lowers_alpha():
    for req in sample_requests():
        out = analyze_alternative_data(req)
        assert _scenario(out, "negative_news_shock").alpha_score < _scenario(out, "base").alpha_score


def test_reliability_downgrade_lowers_quality():
    # Scenario average reliability drops; headline quality = avg reliability × |IC(5d)|.
    for req in sample_requests():
        out = analyze_alternative_data(req)
        assert _scenario(out, "reliability_downgrade").average_reliability < _scenario(out, "base").average_reliability
    out = _analyze()
    sq = out.signal_quality
    expected = (
        sum(e.source_reliability for e in _megacap().events) / len(_megacap().events)
        * abs(sq.information_coefficient_5d)
    )
    assert math.isclose(sq.reliability_weighted_quality, expected, rel_tol=1e-9)


def test_novelty_collapse_lowers_novelty():
    for req in sample_requests():
        out = analyze_alternative_data(req)
        assert _scenario(out, "novelty_collapse").average_novelty < _scenario(out, "base").average_novelty


def test_crowded_cluster_changes_regime():
    out = _analyze()  # megacap base = clean positive
    assert out.risk_regime.regime_id == "clean_positive_signal"
    assert _scenario(out, "crowded_event_cluster").regime_label == "Crowded event risk"


def test_severe_combo_regime():
    out = _analyze()  # megacap: reliability + staleness + leakage triggers
    assert _scenario(out, "severe_combo").regime_label == "Severe alt-data stress"


# --------------------------------------------------------------------------- #
# 20–21. Regime & scenarios presence
# --------------------------------------------------------------------------- #
def test_risk_regime_exists():
    for req in sample_requests():
        reg = analyze_alternative_data(req).risk_regime
        assert reg.regime_id and reg.regime_label and reg.explanation
        assert math.isfinite(reg.score) and 0.0 <= reg.score <= 1.0


def test_regime_variety_across_samples():
    regimes = [analyze_alternative_data(req).risk_regime.regime_id for req in sample_requests()]
    assert regimes == [
        "clean_positive_signal", "low_reliability_signal", "clean_negative_signal",
        "noisy_signal", "stale_signal",
    ]


def test_scenarios_present():
    ids = {s.id for s in _analyze().scenario_results}
    assert {
        "base", "positive_news_burst", "negative_news_shock", "social_noise_spike",
        "reliability_downgrade", "publication_lag_increase", "novelty_collapse",
        "crowded_event_cluster", "leakage_violation", "severe_combo",
    } == ids


# --------------------------------------------------------------------------- #
# 22–25. Validation
# --------------------------------------------------------------------------- #
def test_reject_sentiment_out_of_range():
    base = _megacap().model_dump()
    base["events"][0]["sentiment_score"] = 1.5
    with pytest.raises(ValidationError):
        AlternativeDataAnalysisRequest(**base)


def test_reject_reliability_out_of_range():
    base = _megacap().model_dump()
    base["events"][0]["source_reliability"] = -0.2
    with pytest.raises(ValidationError):
        AlternativeDataAnalysisRequest(**base)


def test_reject_negative_publication_lag():
    base = _megacap().model_dump()
    base["events"][0]["publication_lag_minutes"] = -5.0
    with pytest.raises(ValidationError):
        AlternativeDataAnalysisRequest(**base)


def test_reject_feature_before_event():
    base = _megacap().model_dump()
    base["events"][0]["feature_available_timestamp"] = "2025-12-31T00:00:00Z"
    with pytest.raises(ValidationError):
        AlternativeDataAnalysisRequest(**base)


def test_reject_non_finite():
    base = _megacap().model_dump()
    base["events"][0]["observed_return_5d"] = float("nan")
    with pytest.raises(ValidationError):
        AlternativeDataAnalysisRequest(**base)


# --------------------------------------------------------------------------- #
# 26. JSON-safety
# --------------------------------------------------------------------------- #
def test_no_nan_or_infinity(client):
    for req in sample_requests():
        res = client.post("/alternative-data/analyze", json=req.model_dump())
        assert res.status_code == 200
        _assert_all_finite(res.json())
