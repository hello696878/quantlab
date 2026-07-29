"""
Deterministic Signal Decay demo fixture (v1).

Twenty-four idempotent cases over SYNTHETIC, generic series — no
downloaded, scraped or real financial data, and no network access of any
kind.  Every relationship is hand-computable from two fixed cycles:

    SIGNAL cycle  S = [0.9, -0.4, 0.1, 0.7, -0.8, 0.3, -0.2, 0.5, -0.6, 0.0]
    NOISE  cycle  E = [0.001, -0.002, 0.0015, -0.0005, 0.002,
                       -0.0015, 0.0005, -0.001, 0.0, 0.0005]

Prices compound the stated per-step returns from 100.0, so a horizon-1
forward return at step ``i`` reproduces the stated ``r_i`` exactly.

Upstream demos (Regime, Model Validation, Cost and Factor Diagnostics —
the last cascading Attribution and Portfolio) are seeded through their own
idempotent loaders and then read READ-ONLY; nothing upstream is modified.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

from app.cost_diagnostics import store as cost_store
from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
from app.factor_diagnostics import store as factor_store
from app.factor_diagnostics.demo import seed_demo_factor_diagnostics
from app.model_validation import store as validation_store
from app.model_validation.demo import seed_demo_validation
from app.regime_diagnostics import store as regime_store
from app.regime_diagnostics.demo import seed_demo_regime_diagnostics

from app.signal_decay import service
from app.signal_decay import store

SIGNAL_CYCLE = (0.9, -0.4, 0.1, 0.7, -0.8, 0.3, -0.2, 0.5, -0.6, 0.0)
NOISE_CYCLE = (0.001, -0.002, 0.0015, -0.0005, 0.002,
               -0.0015, 0.0005, -0.001, 0.0, 0.0005)

BASE_START = date(2024, 6, 3)

UPSTREAM_REGIME_KEY = "demo:rd:volatility-trend"
UPSTREAM_REGIME_DEFINITION = "vol"
UPSTREAM_VALIDATION_KEY = "demo:mv:baseline-candidate"
UPSTREAM_COST_KEY = "demo:cd:high-turnover-erosion"
UPSTREAM_FACTOR_KEY = "demo:fd:contemporaneous-descriptive"


def _s(index: int) -> float:
    return SIGNAL_CYCLE[index % len(SIGNAL_CYCLE)]


def _e(index: int) -> float:
    return NOISE_CYCLE[index % len(NOISE_CYCLE)]


def _stamps(count: int, start: date = BASE_START) -> List[str]:
    return [f"{(start + timedelta(days=i)).isoformat()}T00:00:00"
            for i in range(count)]


def _prices_from_returns(stamps: Sequence[str],
                         returns: Sequence[float], *,
                         entity_id: str = "aggregate",
                         price_field: str = "close"
                         ) -> List[Dict[str, Any]]:
    """len(stamps) price rows; returns[i] is the step i -> i+1 return."""
    rows: List[Dict[str, Any]] = []
    level = 100.0
    for i, stamp in enumerate(stamps):
        rows.append({"entity_id": entity_id, "timestamp": stamp,
                     price_field: level})
        if i < len(returns):
            level *= (1.0 + returns[i])
    return rows


def _signal_rows(stamps: Sequence[str], values: Sequence[Optional[float]], *,
                 entity_id: str = "aggregate",
                 explicit_availability: bool = True) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i, stamp in enumerate(stamps):
        row: Dict[str, Any] = {"entity_id": entity_id,
                               "source_timestamp": stamp,
                               "value": values[i]}
        if explicit_availability:
            row["available_at"] = stamp
        rows.append(row)
    return rows


def _signal(signal_id: str, *, signal_type: str = "continuous_score",
            unit: str = "score",
            direction: str = "higher_is_higher_score",
            availability: str = "explicit_available_at",
            transformation: str = "none",
            tie_policy: str = "average", **extra: Any) -> Dict[str, Any]:
    payload = {"signal_id": signal_id, "name": signal_id,
               "signal_type": signal_type,
               "source": "synthetic demo fixture (locally generated)",
               "unit": unit, "frequency": "daily", "direction": direction,
               "availability_policy": availability,
               "transformation": transformation, "tie_policy": tie_policy}
    payload.update(extra)
    return payload


def _outcome_forward() -> Dict[str, Any]:
    return {"outcome_id": "fwd-close", "name": "forward close-to-close return",
            "target_type": "forward_return", "price_field": "close",
            "source": "synthetic demo prices (locally generated)"}


def _single_entity_payload(name: str, *, n: int,
                           step_returns: Sequence[float],
                           signal_values: Sequence[Optional[float]],
                           horizons: List[int], lags: List[int] = [0],
                           explicit_availability: bool = True,
                           availability: str = "explicit_available_at",
                           overlap_policy: str = "overlapping",
                           bucket_count: int = 3,
                           signal_id: str = "demo-signal",
                           **extra: Any) -> Dict[str, Any]:
    stamps = _stamps(n)
    payload: Dict[str, Any] = {
        "name": name,
        "signal": _signal(signal_id, availability=availability),
        "outcome": _outcome_forward(),
        "observations": _signal_rows(
            stamps, signal_values,
            explicit_availability=explicit_availability),
        "prices": _prices_from_returns(stamps, step_returns),
        "horizons": {"horizons": horizons, "unit": "observations",
                     "entry_lags": lags, "overlap_policy": overlap_policy},
        "buckets": {"bucket_count": bucket_count, "scope": "global",
                    "minimum_per_bucket": 2},
    }
    payload.update(extra)
    return payload


def seed_demo_signal_decay() -> Dict[str, Any]:
    """Idempotent: loading twice creates nothing new."""
    seed_demo_regime_diagnostics()
    seed_demo_validation()
    seed_demo_cost_diagnostics()
    seed_demo_factor_diagnostics()   # cascades attribution + portfolio

    created = 0
    skipped = 0
    run_ids: List[int] = []
    notes: List[str] = []

    def seed(key: str, payload: Dict[str, Any], *, baseline: bool = False,
             experiment: bool = False, note: str = "") -> Optional[int]:
        nonlocal created, skipped
        existing = store.run_demo_key_id(key)
        if existing is not None:
            skipped += 1
            run_ids.append(existing)
            return existing
        run = service.create_run(payload, demo_key=key)
        try:
            service.execute_run(run["id"], create_experiment=experiment)
        except (*service.ENGINE_ERRORS, service.ConflictError):
            pass  # honest-refusal cases store their failure message
        if baseline:
            try:
                service.mark_baseline(run["id"])
            except service.ConflictError:
                pass
        created += 1
        run_ids.append(run["id"])
        if note:
            notes.append(note)
        return run["id"]

    n = 40

    # 1. Perfect positive one-horizon relationship: r_i = 0.01 * s_i.
    # A tiny index-scaled epsilon makes every cycle value unique so the
    # rank correlation has no ties to break.
    unique = [_s(i) + i * 1e-6 for i in range(n)]
    seed("demo:sd:perfect-positive", _single_entity_payload(
        "Perfect positive one-horizon relationship", n=n,
        step_returns=[0.01 * unique[i] for i in range(n - 1)],
        signal_values=unique,
        horizons=[1],
        description=(
            "r_i = 0.01 x signal_i exactly (unique signal values), so the "
            "horizon-1 Pearson and Spearman correlations are 1.000000 over "
            "this sample. A perfect in-sample association is still only a "
            "description of this sample.")),
        note="horizon-1 Pearson and Spearman exactly 1")

    # 2. Perfect negative relationship.
    seed("demo:sd:perfect-negative", _single_entity_payload(
        "Perfect negative relationship", n=n,
        step_returns=[-0.01 * unique[i] for i in range(n - 1)],
        signal_values=unique,
        horizons=[1],
        description="r_i = -0.01 x signal_i exactly: correlations are -1."),
        note="horizon-1 correlations exactly -1")

    # 3. Noisy weak relationship.
    seed("demo:sd:noisy-weak", _single_entity_payload(
        "Noisy weak relationship", n=n,
        step_returns=[0.0008 * _s(i) + _e(i) for i in range(n - 1)],
        signal_values=[_s(i) for i in range(n)],
        horizons=[1],
        description=(
            "A small signal component under a larger deterministic noise "
            "cycle; the measured association is weak and its p-value is the "
            "real scipy value.")),
        note="weak association with a real p-value")

    # 4. Constant signal.
    seed("demo:sd:constant-signal", _single_entity_payload(
        "Constant signal (statistics unavailable)", n=n,
        step_returns=[0.01 * _s(i) for i in range(n - 1)],
        signal_values=[0.5] * n,
        horizons=[1],
        description=(
            "Every signal value is 0.5: no correlation is defined, so every "
            "statistic is unavailable with that reason — never 0, never "
            "NaN.")),
        note="constant signal -> unavailable with reason")

    # 5. Constant outcome.
    seed("demo:sd:constant-outcome", _single_entity_payload(
        "Constant outcome (statistics unavailable)", n=n,
        step_returns=[0.0] * (n - 1),
        signal_values=[_s(i) for i in range(n)],
        horizons=[1],
        description="Prices never move, so every outcome is exactly zero and "
                    "no correlation is defined."),
        note="constant outcome -> unavailable with reason")

    # 6. Heavy signal ties.
    seed("demo:sd:heavy-ties", _single_entity_payload(
        "Heavy signal ties", n=n,
        step_returns=[0.01 * (1.0 if i % 3 == 0 else 0.0)
                      for i in range(n - 1)],
        signal_values=[1.0 if i % 3 == 0 else 0.0 for i in range(n)],
        horizons=[1],
        description=(
            "A binary-style score with heavy ties: tie counts are reported, "
            "Spearman uses average ranks (documented) and the tie policy is "
            "part of the stored definition.")),
        note="tie counts visible, average-rank Spearman")

    # 7. Missing observations.
    missing_values: List[Optional[float]] = [
        None if i % 7 == 3 else _s(i) for i in range(n)]
    missing_prices = _prices_from_returns(
        _stamps(n), [0.01 * _s(i) for i in range(n - 1)])
    missing_prices[11]["close"] = None  # an explicit price gap
    payload = _single_entity_payload(
        "Missing observations stay missing", n=n,
        step_returns=[0.01 * _s(i) for i in range(n - 1)],
        signal_values=missing_values,
        horizons=[1],
        description=(
            "Null signal values and a null price leave their pairs "
            "unavailable with reasons; nothing is forward-filled or "
            "interpolated."))
    payload["prices"] = missing_prices
    seed("demo:sd:missing-observations", payload,
         note="unavailable pairs listed with reasons")

    # 8. Cross-sectional rank-IC example: 6 entities, rank IC = 1 per stamp.
    stamps_cs = _stamps(25)
    entities = [f"e{k}" for k in range(1, 7)]
    observations_cs: List[Dict[str, Any]] = []
    prices_cs: List[Dict[str, Any]] = []
    for k, entity in enumerate(entities):
        values = [float((i + k) % 6 + 1) for i in range(len(stamps_cs))]
        observations_cs.extend(_signal_rows(stamps_cs, values,
                                            entity_id=entity))
        returns = [0.001 * values[i] for i in range(len(stamps_cs) - 1)]
        prices_cs.extend(_prices_from_returns(stamps_cs, returns,
                                              entity_id=entity))
    seed("demo:sd:cross-sectional-ic", {
        "name": "Cross-sectional rank IC (each stamp its own universe)",
        "signal": _signal("cs-signal",
                          transformation="rank_cross_sectional"),
        "outcome": _outcome_forward(),
        "observations": observations_cs,
        "prices": prices_cs,
        "horizons": {"horizons": [1], "unit": "observations",
                     "entry_lags": [0]},
        "buckets": {"bucket_count": 3, "scope": "per_timestamp",
                    "minimum_per_bucket": 2},
        "description": (
            "Six entities whose next-step return is 0.001 x their "
            "contemporaneous score: every timestamp's Spearman rank IC over "
            "its own eligible universe is 1, so the mean rank IC is 1. "
            "Ranks use only the contemporaneous universe — never the "
            "future."),
    }, note="mean cross-sectional rank IC exactly 1")

    # 9. Time-series lagged example (verified_trailing_signal).
    seed("demo:sd:time-series-lagged", _single_entity_payload(
        "Time-series lagged signal (entry lag 1)", n=n,
        step_returns=[0.01 * _s(max(0, i - 1)) for i in range(n - 1)],
        signal_values=[_s(i) for i in range(n)],
        horizons=[1], lags=[1],
        explicit_availability=False, availability="same_timestamp",
        description=(
            "Availability is assumed to equal each observation's own stamp "
            "(same_timestamp) and entry waits one stored step, so the state "
            "is verified_trailing_signal: r at step i+1 equals 0.01 x "
            "signal_i.")),
        note="verified_trailing_signal with lag 1")

    # 10. Decaying relationship across horizons.
    n_decay = 60
    decay_returns = [0.01 * _s(i) + 0.004 * _s(i - 1) + 0.0015 * _s(i - 2)
                     + 0.3 * _e(i) for i in range(n_decay - 1)]
    seed("demo:sd:decay-curve", _single_entity_payload(
        "Decaying association across horizons", n=n_decay,
        step_returns=decay_returns,
        signal_values=[_s(i) for i in range(n_decay)],
        horizons=[1, 2, 3, 5, 8],
        description=(
            "The step return loads mostly on the current signal with small "
            "trailing terms, so the per-horizon rank correlation weakens as "
            "the horizon grows. The decay summary reports where the "
            "statistic first weakens — never which horizon is 'best'.")),
        note="decay curve across horizons 1..8")

    # 11. Sign-changing horizon example.
    n_sign = 60
    sign_returns = [0.02 * _s(i) - 0.035 * _s(i - 3)
                    for i in range(n_sign - 1)]
    seed("demo:sd:sign-change", _single_entity_payload(
        "Sign-changing association", n=n_sign,
        step_returns=sign_returns,
        signal_values=[_s(i) for i in range(n_sign)],
        horizons=[1, 2, 4, 6],
        description=(
            "A delayed opposite-sign term makes the measured association "
            "positive at short horizons and negative once the horizon "
            "covers the reversal. The first sign-change horizon is reported "
            "as a location in this sample.")),
        note="sign change across horizons")

    # 12. Overlapping-horizon example.
    seed("demo:sd:overlapping", _single_entity_payload(
        "Overlapping horizon-4 intervals", n=n,
        step_returns=[0.01 * _s(i) + 0.5 * _e(i) for i in range(n - 1)],
        signal_values=[_s(i) for i in range(n)],
        horizons=[4],
        description=(
            "Consecutive signals with a 4-step horizon: every interval "
            "overlaps its neighbours. The overlap ratio, the maximum "
            "simultaneous overlap and the p-value limitation are all "
            "visible.")),
        note="overlap ratio and p-value limitation visible")

    # 13. Deterministic non-overlapping example.
    seed("demo:sd:non-overlapping", _single_entity_payload(
        "Deterministic non-overlapping selection", n=n,
        step_returns=[0.01 * _s(i) + 0.5 * _e(i) for i in range(n - 1)],
        signal_values=[_s(i) for i in range(n)],
        horizons=[4], overlap_policy="non_overlapping",
        description=(
            "The same data under the documented non-overlap policy: keep "
            "the earliest pair, then the next pair whose entry is at or "
            "after the previous exit. Both the overlapping and the selected "
            "rows are stored.")),
        note="earliest-first non-overlap selection")

    # 14. Quantile monotonic example.
    unique60 = [_s(i) + i * 1e-6 for i in range(60)]
    seed("demo:sd:monotonic-buckets", _single_entity_payload(
        "Monotonic quantile buckets", n=60,
        step_returns=[0.01 * unique60[i] for i in range(59)],
        signal_values=unique60,
        horizons=[1], bucket_count=5,
        description=(
            "r = 0.01 x signal makes bucket means strictly increasing in "
            "the bucket ordinal. Monotonic bucket means describe this "
            "sample; they do not prove predictability.")),
        note="five monotone buckets")

    # 15. Non-monotonic bucket example.
    seed("demo:sd:non-monotonic-buckets", _single_entity_payload(
        "Non-monotonic (U-shaped) buckets", n=60,
        step_returns=[0.01 * abs(_s(i)) for i in range(59)],
        signal_values=[_s(i) for i in range(60)],
        horizons=[1], bucket_count=5,
        description=(
            "r = 0.01 x |signal|: extreme buckets outperform the middle, so "
            "adjacent-bucket violations are non-zero and reported "
            "neutrally.")),
        note="U-shape with visible monotonicity violations")

    # 16. High-turnover signal (ranks rotate every stamp).
    stamps_t = _stamps(20)
    observations_high: List[Dict[str, Any]] = []
    prices_high: List[Dict[str, Any]] = []
    for k, entity in enumerate(entities):
        values = [float((i * 2 + k * 3) % 7) for i in range(len(stamps_t))]
        observations_high.extend(_signal_rows(stamps_t, values,
                                              entity_id=entity))
        prices_high.extend(_prices_from_returns(
            stamps_t, [0.001 * values[i] for i in range(len(stamps_t) - 1)],
            entity_id=entity))
    seed("demo:sd:high-turnover", {
        "name": "High-turnover signal (membership churns)",
        "signal": _signal("churn-signal",
                          transformation="rank_cross_sectional"),
        "outcome": _outcome_forward(),
        "observations": observations_high,
        "prices": prices_high,
        "horizons": {"horizons": [1], "unit": "observations",
                     "entry_lags": [0]},
        "buckets": {"bucket_count": 3, "scope": "per_timestamp",
                    "minimum_per_bucket": 1},
        "description": (
            "Scores rotate across entities every stamp, so top-bucket "
            "membership churns: entries, exits, Jaccard similarity and "
            "one-way turnover are all high."),
    }, note="high one-way turnover and low Jaccard")

    # 17. Stable-membership low-turnover signal.
    observations_low: List[Dict[str, Any]] = []
    prices_low: List[Dict[str, Any]] = []
    for k, entity in enumerate(entities):
        values = [float(k)] * len(stamps_t)
        observations_low.extend(_signal_rows(stamps_t, values,
                                             entity_id=entity))
        prices_low.extend(_prices_from_returns(
            stamps_t, [0.0005 * k] * (len(stamps_t) - 1), entity_id=entity))
    seed("demo:sd:low-turnover", {
        "name": "Stable-membership low-turnover signal",
        "signal": _signal("stable-signal",
                          transformation="rank_cross_sectional",
                          tie_policy="first"),
        "outcome": _outcome_forward(),
        "observations": observations_low,
        "prices": prices_low,
        "horizons": {"horizons": [1], "unit": "observations",
                     "entry_lags": [0]},
        "buckets": {"bucket_count": 3, "scope": "per_timestamp",
                    "minimum_per_bucket": 1},
        "description": (
            "Constant per-entity scores keep membership fixed: after the "
            "first rebalance the one-way turnover is 0 and the Jaccard "
            "similarity is 1. The first rebalance's turnover is null under "
            "the declared no-prior policy."),
    }, note="turnover 0 and Jaccard 1 after the first rebalance")

    # 18. Implementation-delay degradation example.
    seed("demo:sd:implementation-lag", _single_entity_payload(
        "Implementation-delay degradation", n=60,
        step_returns=[0.01 * _s(i) + 0.3 * _e(i) for i in range(59)],
        signal_values=[_s(i) for i in range(60)],
        horizons=[1, 2], lags=[0, 1, 2],
        description=(
            "The step return loads on the CURRENT signal, so entering one "
            "or two steps late measures the association against later, "
            "unrelated steps: the rank correlation degrades as the entry "
            "lag grows. Delayed entry shifts BOTH entry and exit stamps; "
            "the holding length stays the configured horizon. No lag is "
            "called optimal.")),
        note="association degrades with entry lag")

    # 19. Cost-adjusted gross-positive / net-nonpositive reference.
    cost_run_id = cost_store.run_demo_key_id(UPSTREAM_COST_KEY)
    if cost_run_id is not None:
        stamps_c = _stamps(20)
        observations_cost: List[Dict[str, Any]] = []
        prices_cost: List[Dict[str, Any]] = []
        for k, entity in enumerate(entities):
            values = [float((i + k) % 6 + 1) for i in range(len(stamps_c))]
            observations_cost.extend(_signal_rows(stamps_c, values,
                                                  entity_id=entity))
            prices_cost.extend(_prices_from_returns(
                stamps_c,
                [0.00002 * values[i] for i in range(len(stamps_c) - 1)],
                entity_id=entity))
        seed("demo:sd:cost-adjusted", {
            "name": "Gross-positive, cost-adjusted non-positive reference",
            "signal": _signal("cost-signal",
                              transformation="rank_cross_sectional"),
            "outcome": _outcome_forward(),
            "observations": observations_cost,
            "prices": prices_cost,
            "horizons": {"horizons": [1], "unit": "observations",
                         "entry_lags": [0]},
            "buckets": {"bucket_count": 3, "scope": "per_timestamp",
                        "minimum_per_bucket": 1},
            "cost_diagnostic_run_id": cost_run_id,
            "policy": {"reference_notional": 100000.0},
            "description": (
                "A tiny gross top-minus-bottom spread against the linked "
                "Phase 55 basis-point cost model at an explicit reference "
                "notional: the gross spread is positive and the "
                "cost-adjusted spread is not. Gross and cost-adjusted "
                "figures stay separate, and unavailable cost components "
                "stay unavailable."),
        }, note="gross positive, cost-adjusted non-positive")

    # 20. Rare-regime example.
    regime_id = regime_store.run_demo_key_id(UPSTREAM_REGIME_KEY)
    if regime_id is not None:
        rrun = regime_store.get_run(regime_id)
        regime_stamps = (rrun.get("timestamps") or [])[30:90]
        if len(regime_stamps) >= 40:
            m = len(regime_stamps)
            payload = {
                "name": "Signal decay by STORED regime (rare regime visible)",
                "signal": _signal("regime-signal"),
                "outcome": _outcome_forward(),
                "observations": [
                    {"entity_id": "aggregate", "source_timestamp": s,
                     "available_at": s, "value": _s(i)}
                    for i, s in enumerate(regime_stamps)],
                "prices": [
                    {"entity_id": "aggregate", "timestamp": s,
                     "close": p["close"]}
                    for s, p in zip(regime_stamps, _prices_from_returns(
                        regime_stamps,
                        [0.01 * _s(i) + 0.3 * _e(i) for i in range(m - 1)]))],
                "horizons": {"horizons": [1, 3], "unit": "observations",
                             "entry_lags": [0]},
                "buckets": {"bucket_count": 3, "scope": "global",
                            "minimum_per_bucket": 2},
                "regime_run_id": regime_id,
                "regime_definition_id": UPSTREAM_REGIME_DEFINITION,
                "description": (
                    "Pairs are bucketed by the stored Phase 54 volatility "
                    "assignment (never recomputed); a regime with fewer "
                    "than 10 observations is marked rare and its statistics "
                    "are withheld."),
            }
            seed("demo:sd:regime-linked", payload,
                 note="rare regimes withheld, fingerprints pinned")

    # 21. Held-out validation example.
    validation_id = validation_store.run_demo_key_id(UPSTREAM_VALIDATION_KEY)
    if validation_id is not None:
        vrun = validation_store.get_run(validation_id)
        splits = validation_store.list_splits(validation_id)
        sample_stamps = [s["prediction_time"] for s in (vrun or {}).get(
            "samples", []) if s.get("prediction_time")]
        if vrun and splits and len(sample_stamps) >= 20:
            m = len(sample_stamps)
            seed("demo:sd:held-out-validation", {
                "name": "Held-out evaluation on a stored validation split",
                "signal": _signal("validated-signal"),
                "outcome": _outcome_forward(),
                "observations": [
                    {"entity_id": "aggregate", "source_timestamp": s,
                     "available_at": s, "value": _s(i)}
                    for i, s in enumerate(sample_stamps)],
                "prices": [
                    {"entity_id": "aggregate", "timestamp": s,
                     "close": p["close"]}
                    for s, p in zip(sample_stamps, _prices_from_returns(
                        sample_stamps,
                        [0.01 * _s(i) + 0.3 * _e(i)
                         for i in range(m - 1)]))],
                "horizons": {"horizons": [1], "unit": "observations",
                             "entry_lags": [0]},
                "buckets": {"bucket_count": 3, "scope": "global",
                            "minimum_per_bucket": 2},
                "validation_run_id": validation_id,
                "validation_split_label": splits[0]["split_label"],
                "description": (
                    "Training, held-out and full-sample diagnostics are "
                    "reported separately; bucket thresholds come from the "
                    "TRAINING observations only and are applied frozen to "
                    "held-out observations, with purge and embargo "
                    "membership used exactly as stored."),
            }, note="train/held-out separation with frozen thresholds")

    # 22. Future-looking invalid example.
    stamps_invalid = _stamps(12)
    seed("demo:sd:future-looking-invalid", {
        "name": "Future-looking outcome (declared INVALID)",
        "signal": _signal("late-signal"),
        "outcome": {"outcome_id": "supplied-window",
                    "name": "supplied outcome window",
                    "target_type": "supplied_outcome", "unit": "score",
                    "source": "synthetic demo fixture"},
        "observations": [
            {"entity_id": "aggregate", "source_timestamp": s,
             "available_at": _stamps(13)[i + 1], "value": _s(i)}
            for i, s in enumerate(stamps_invalid)],
        "supplied_outcomes": [
            {"entity_id": "aggregate", "signal_timestamp": s,
             "period_start": s,
             "period_end": _stamps(13)[i + 1],
             "value": 0.01 * _s(i)}
            for i, s in enumerate(stamps_invalid)],
        "horizons": {"unit": "observations"},
        "buckets": {"bucket_count": 2, "scope": "global",
                    "minimum_per_bucket": 2},
        "description": (
            "Every signal only became available AFTER the outcome window it "
            "is paired with began, so the run is INVALID: the first offence "
            "is recorded with its timestamps and the run can never become a "
            "baseline."),
    }, note="invalid timing, baseline refused")

    # 23. Factor-residualised comparison example.
    factor_id = factor_store.run_demo_key_id(UPSTREAM_FACTOR_KEY)
    if factor_id is not None:
        periods = factor_store.list_periods(factor_id)
        factor_stamps = [p["period_start"] for p in periods]
        if len(factor_stamps) >= 20:
            m = len(factor_stamps)
            seed("demo:sd:factor-residual", {
                "name": "Raw versus factor-residualised outcomes",
                "signal": _signal("residual-signal"),
                "outcome": _outcome_forward(),
                "observations": [
                    {"entity_id": "aggregate", "source_timestamp": s,
                     "available_at": s, "value": _s(i)}
                    for i, s in enumerate(factor_stamps)],
                "prices": [
                    {"entity_id": "aggregate", "timestamp": s,
                     "close": p["close"]}
                    for s, p in zip(factor_stamps, _prices_from_returns(
                        factor_stamps,
                        [0.01 * _s(i) + 0.3 * _e(i)
                         for i in range(m - 1)]))],
                "horizons": {"horizons": [1], "unit": "observations",
                             "entry_lags": [0]},
                "buckets": {"bucket_count": 3, "scope": "global",
                            "minimum_per_bucket": 2},
                "factor_run_id": factor_id,
                "description": (
                    "The same signal against raw outcomes and against the "
                    "linked Phase 59 run's stored per-period residuals "
                    "(summed over each interval, read-only). The two scopes "
                    "are separate rows; a residual association is not "
                    "alpha, and nothing is neutralised automatically."),
            }, note="raw and factor-residual scopes side by side")

    # 24. Valid baseline candidate.
    seed("demo:sd:baseline-candidate", _single_entity_payload(
        "Baseline candidate (point-in-time, complete)", n=60,
        step_returns=[0.01 * _s(i) + 0.3 * _e(i) for i in range(59)],
        signal_values=[_s(i) for i in range(60)],
        horizons=[1, 2], bucket_count=3,
        policy={"multiple_testing": {
            "methods": ["bonferroni", "holm", "bh"], "alpha": 0.05,
            "family": "Spearman p-values of the two evaluated horizons"},
            "bootstrap": {"method": "iid", "seed": 60, "resamples": 200,
                          "statistic": "spearman"}},
        description=(
            "Explicit availability at every observation, forward returns "
            "from stored prices, complete results: the only combination "
            "this lab accepts as a comparison baseline. A baseline is a "
            "comparison reference only — never chosen by IC, spread, "
            "cost-adjusted return or decay length.")),
        baseline=True, experiment=True,
        note="eligible baseline with multiple testing and bootstrap")

    return {"created": created > 0, "created_count": created,
            "skipped_count": skipped, "run_ids": run_ids, "notes": notes}


__all__ = ["seed_demo_signal_decay", "SIGNAL_CYCLE", "NOISE_CYCLE",
           "_s", "_e", "_stamps", "_prices_from_returns", "_signal_rows"]
