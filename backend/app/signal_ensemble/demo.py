"""
Deterministic Signal Ensemble demo fixture (v1).

Twenty-four idempotent cases over SYNTHETIC, generic series — no
downloaded, scraped or real financial data, and no network access.  The
Phase 60 demo cycles are reused so every relationship stays
hand-computable; upstream demos (Regime, Model Validation, Cost, Factor —
the last cascading Attribution and Portfolio) are seeded through their own
idempotent loaders and then read READ-ONLY.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.cost_diagnostics import store as cost_store
from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
from app.factor_diagnostics import store as factor_store
from app.factor_diagnostics.demo import seed_demo_factor_diagnostics
from app.model_validation import store as validation_store
from app.model_validation.demo import seed_demo_validation
from app.regime_diagnostics import store as regime_store
from app.regime_diagnostics.demo import seed_demo_regime_diagnostics

from app.signal_decay.demo import (
    _e, _prices_from_returns, _s, _stamps,
)
from app.signal_decay.demo import (
    UPSTREAM_COST_KEY, UPSTREAM_FACTOR_KEY, UPSTREAM_REGIME_DEFINITION,
    UPSTREAM_REGIME_KEY, UPSTREAM_VALIDATION_KEY,
)

from app.signal_ensemble import service
from app.signal_ensemble import store

#: A second deterministic cycle with a different ordering than the Phase 60
#: SIGNAL cycle, so cross-cycle correlations are moderate by construction.
ALT_CYCLE = (0.2, 0.8, -0.5, -0.1, 0.6, -0.9, 0.4, 0.0, -0.3, 0.7)


def _a(index: int) -> float:
    return ALT_CYCLE[index % len(ALT_CYCLE)]


def _definition(signal_id: str, *, unit: str = "score",
                availability: str = "explicit_available_at",
                direction: str = "higher_is_higher_score",
                transformation: str = "none") -> Dict[str, Any]:
    return {"signal_id": signal_id, "name": signal_id,
            "signal_type": "continuous_score",
            "source": "synthetic demo fixture (locally generated)",
            "unit": unit, "frequency": "daily", "direction": direction,
            "availability_policy": availability,
            "transformation": transformation, "tie_policy": "average"}


def _rows(stamps: List[str], values: List[Optional[float]], *,
          entity_id: str = "aggregate",
          explicit: bool = True) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for stamp, value in zip(stamps, values):
        row: Dict[str, Any] = {"entity_id": entity_id,
                               "source_timestamp": stamp, "value": value}
        if explicit:
            row["available_at"] = stamp
        rows.append(row)
    return rows


def _universe(signals: Dict[str, List[Dict[str, Any]]], *,
              alignment: str = "strict_intersection",
              availability: str = "explicit_available_at",
              units: Optional[Dict[str, str]] = None
              ) -> Dict[str, Any]:
    return {
        "name": "demo universe",
        "signals": [_definition(signal_id,
                                unit=(units or {}).get(signal_id, "score"),
                                availability=availability)
                    for signal_id in sorted(signals)],
        "observations": signals,
        "alignment_policy": alignment,
    }


def seed_demo_signal_ensemble() -> Dict[str, Any]:
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

    n = 30
    stamps = _stamps(n)
    base = [_s(i) + i * 1e-6 for i in range(n)]  # unique, tie-free

    # 1. Two identical signals.
    seed("demo:sen:identical", {
        "name": "Identical pair (correlation exactly 1)",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-b": _rows(stamps, list(base)),
        }),
        "description": ("Two byte-identical series: Pearson and Spearman "
                        "are exactly 1 over the strict intersection. A "
                        "perfect sample correlation is still not proof of "
                        "duplicate information."),
    }, note="pairwise correlations exactly 1")

    # 2. Exact negative signal.
    seed("demo:sen:inverse", {
        "name": "Inverse pair (correlation exactly -1)",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-neg": _rows(stamps, [-v for v in base]),
        }),
        "description": ("sig-neg = -sig-a exactly: correlations are -1. "
                        "No inversion is recommended and the negative "
                        "similarity is a description of this sample."),
    }, note="pairwise correlations exactly -1")

    # 3. Independent-looking deterministic signals (assumed availability,
    # so the run stays contemporaneous_descriptive and is the demo's
    # deliberately baseline-INELIGIBLE case).
    seed("demo:sen:independent-looking", {
        "name": "Independent-looking deterministic pair",
        "universe": _universe({
            "sig-a": _rows(stamps, base, explicit=False),
            "sig-alt": _rows(stamps, [_a(i) + i * 1e-6
                                      for i in range(n)], explicit=False),
        }, availability="same_timestamp"),
        "description": ("Two different deterministic cycles with a "
                        "moderate measured association and ASSUMED "
                        "availability (same_timestamp), so the run stays "
                        "contemporaneous and descriptive. Low correlation "
                        "in this sample never proves independent "
                        "information."),
    }, note="moderate association, descriptive availability")

    # 4. Constant signal.
    seed("demo:sen:constant", {
        "name": "Constant signal (pairwise unavailable)",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-const": _rows(stamps, [0.5] * n),
        }),
        "description": ("One component never moves, so no correlation is "
                        "defined: the pairwise row is unavailable with "
                        "that reason — never zero and never a fabricated "
                        "number."),
    }, note="constant component -> unavailable with reason")

    # 5. Heavy-tie signal.
    seed("demo:sen:heavy-ties", {
        "name": "Heavy-tie pair (tie counts visible)",
        "universe": _universe({
            "bin-a": _rows(stamps, [1.0 if i % 3 == 0 else 0.0
                                    for i in range(n)]),
            "bin-b": _rows(stamps, [1.0 if i % 2 == 0 else 0.0
                                    for i in range(n)]),
        }),
        "description": ("Binary-style components: tie counts are "
                        "reported, Spearman uses documented average "
                        "ranks, and sign agreement carries its zero-sign "
                        "count."),
    }, note="tie counts and zero-sign counts visible")

    # 6. Missing-overlap signal.
    early = _stamps(10)
    late = _stamps(10)[-2:] + _stamps(24)[10:]
    seed("demo:sen:missing-overlap", {
        "name": "Insufficient overlap (unavailable with reason)",
        "universe": _universe({
            "sig-early": _rows(early, [_s(i) for i in range(10)]),
            "sig-late": _rows(late[:14], [_a(i) for i in range(14)]),
        }),
        "description": ("The two components share fewer overlapping "
                        "observations than the configured minimum, so the "
                        "pairwise statistics are unavailable with the "
                        "overlap count on the row."),
    }, note="thin overlap -> unavailable, count disclosed")

    # 7. Pairwise-complete versus strict intersection.
    gappy = [None if 8 <= i < 20 else _a(i) + i * 1e-6 for i in range(n)]
    seed("demo:sen:pairwise-complete", {
        "name": "Pairwise-complete versus strict intersection",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-b": _rows(stamps, [0.8 * v + 0.1 for v in base]),
            "sig-gappy": _rows(stamps, gappy),
        }, alignment="pairwise_complete"),
        "description": ("One component has a stored-null block, so the "
                        "strict intersection shrinks to 18 keys while the "
                        "full a/b pair keeps 30. Both alignment modes are "
                        "stored with pair-specific sample counts; matrix "
                        "diagnostics use only the strict intersection."),
    }, note="strict 18 keys vs pairwise 30 on the full pair")

    # 8. Highly redundant three-signal set.
    seed("demo:sen:redundant-trio", {
        "name": "Highly redundant trio (effective count near 1)",
        "universe": _universe({
            "red-1": _rows(stamps, base),
            "red-2": _rows(stamps, [v * 1.2 + 0.05 for v in base]),
            "red-3": _rows(stamps, [v * 0.7 - 0.02 for v in base]),
        }),
        "similarity": {"clustering": {"linkage": "average",
                                      "threshold": 0.5}},
        "description": ("Three affine copies of one cycle: every pairwise "
                        "correlation is exactly 1, the effective signal "
                        "count is 1.0 (a matrix-concentration diagnostic, "
                        "not a truth about information), and clustering "
                        "at threshold 0.5 yields one cluster."),
    }, note="effective count exactly 1, one cluster")

    # 9. Lower-redundancy signal set.
    seed("demo:sen:diverse-trio", {
        "name": "Lower-redundancy trio",
        "universe": _universe({
            "div-1": _rows(stamps, base),
            "div-2": _rows(stamps, [_a(i) + i * 1e-6 for i in range(n)]),
            "div-3": _rows(stamps, [_s(i + 5) - i * 1e-6
                                    for i in range(n)]),
        }),
        "similarity": {"clustering": {"linkage": "average",
                                      "threshold": 0.5}},
        "description": ("Three different cycles: lower mean absolute "
                        "correlation and an effective signal count "
                        "closer to the signal count — still only a "
                        "matrix-concentration description."),
    }, note="higher effective count than the redundant trio")

    # 10. Equal-weight combination (with outcomes).
    step_returns = [0.01 * base[i] + 0.3 * _e(i) for i in range(n - 1)]
    prices = _prices_from_returns(stamps, step_returns)
    seed("demo:sen:equal-weight", {
        "name": "Equal-weight combination reference",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-b": _rows(stamps, [0.9 * v + 0.03 for v in base]),
        }),
        "prices": prices,
        "analysis": {"horizons": [1, 3], "entry_lags": [0]},
        "description": ("combined = (a + b) / 2 per observation; the "
                        "combination and both components are evaluated "
                        "side by side through the Phase 60 policies. "
                        "Nothing claims the ensemble improves "
                        "predictability."),
    }, note="equal-weight combination with horizon rows")

    # 11. User-supplied static weights.
    seed("demo:sen:user-weights", {
        "name": "User-supplied static weights (0.7 / 0.3)",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-b": _rows(stamps, [_a(i) + i * 1e-6 for i in range(n)]),
        }),
        "combination": {"mode": "user_weights",
                        "weights": {"sig-a": 0.7, "sig-b": 0.3},
                        "weight_normalisation": "require_sum_to_one"},
        "prices": prices,
        "analysis": {"horizons": [1], "entry_lags": [0]},
        "description": ("Static user weights 0.7/0.3 under "
                        "require_sum_to_one; configured and effective "
                        "weights are both stored, and no weight was "
                        "derived from any historical result."),
    }, note="static 0.7/0.3 weights, sum-to-one validated")

    # 12. Negative-weight combination.
    seed("demo:sen:negative-weight", {
        "name": "Explicit negative weight (long/short reference)",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-b": _rows(stamps, [0.5 * v + 0.2 for v in base]),
        }),
        "combination": {"mode": "user_weights",
                        "weights": {"sig-a": 1.5, "sig-b": -0.5},
                        "allow_negative_weights": True,
                        "weight_normalisation": "require_sum_to_one"},
        "description": ("An explicitly declared negative weight under "
                        "allow_negative_weights; gross weight 2.0 and "
                        "net weight 1.0 are disclosed, with no hidden "
                        "leverage and no long-only conversion."),
    }, note="declared negative weight, gross/net disclosed")

    # 13. Require-all missing policy.
    with_gaps = [None if i % 7 == 3 else base[i] for i in range(n)]
    seed("demo:sen:require-all", {
        "name": "Require-all missing policy (unavailable rows visible)",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-gap": _rows(stamps, with_gaps),
        }),
        "description": ("One component has stored nulls; under "
                        "require_all the combined score at those stamps "
                        "is unavailable with the missing component ids "
                        "listed — never zero-imputed, never carried "
                        "forward."),
    }, note="require_all leaves gaps unavailable")

    # 14. Renormalise-available missing policy.
    seed("demo:sen:renormalise-available", {
        "name": "Renormalise-available missing policy (explicit opt-in)",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-b": _rows(stamps, [0.8 * v - 0.01 for v in base]),
            "sig-gap": _rows(stamps, with_gaps),
        }),
        "combination": {"mode": "equal_weight",
                        "missing_component_policy": "renormalise_available",
                        "minimum_component_count": 2},
        "description": ("The same gaps under the explicitly selected "
                        "renormalise_available policy: available "
                        "components' weights are renormalised, the "
                        "missing ids, effective component count and "
                        "effective weights all stay visible."),
    }, note="renormalisation only by explicit selection")

    # 15. Component-contribution reconciliation.
    seed("demo:sen:reconciliation", {
        "name": "Component-contribution reconciliation",
        "universe": _universe({
            "sig-a": _rows(stamps, base),
            "sig-b": _rows(stamps, [_a(i) for i in range(n)]),
            "sig-c": _rows(stamps, [0.25 * v for v in base]),
        }),
        "combination": {"mode": "user_weights",
                        "weights": {"sig-a": 0.5, "sig-b": 0.3,
                                    "sig-c": 0.2},
                        "weight_normalisation": "require_sum_to_one"},
        "description": ("Every stored observation's combined score equals "
                        "the sum of its component contributions "
                        "(effective weight x oriented normalised value) "
                        "within 1e-9; the reconciliation state is on the "
                        "run and nothing is redistributed."),
    }, note="contribution sum equals combined score")

    # 16. High-turnover components, lower combination turnover.
    entities = ["e1", "e2", "e3", "e4"]
    stamps_t = _stamps(12)
    obs_a: List[Dict[str, Any]] = []
    obs_b: List[Dict[str, Any]] = []
    price_rows: List[Dict[str, Any]] = []
    for k, entity in enumerate(entities):
        values_a = [float((t + k) % 4) + k * 1e-3
                    for t in range(len(stamps_t))]
        values_b = [3.0 - float((t + k) % 4) for t in range(len(stamps_t))]
        obs_a.extend(_rows(stamps_t, values_a, entity_id=entity))
        obs_b.extend(_rows(stamps_t, values_b, entity_id=entity))
        price_rows.extend(_prices_from_returns(
            stamps_t, [0.001 * ((t + k) % 4)
                       for t in range(len(stamps_t) - 1)],
            entity_id=entity))
    seed("demo:sen:churn-cancel", {
        "name": "Churning components, stable combination",
        "universe": _universe({"churn-a": obs_a, "churn-b": obs_b}),
        "combination": {"mode": "equal_weight"},
        "prices": price_rows,
        "analysis": {"horizons": [1], "entry_lags": [0],
                     "bucket": {"bucket_count": 2, "scope":
                                "per_timestamp",
                                "minimum_per_bucket": 1}},
        "description": ("Both components rotate their rankings every "
                        "stamp (high one-way turnover) while their sum "
                        "is a stable entity ladder (combination turnover "
                        "0 after the first build). Lower turnover is a "
                        "measurement, not a reason the combination is "
                        "better."),
    }, note="component churn cancels in the combination")

    # 17. Low-turnover components, higher combination turnover.
    obs_c: List[Dict[str, Any]] = []
    obs_d: List[Dict[str, Any]] = []
    for k, entity in enumerate(entities):
        values_c = [float(k) for _ in range(len(stamps_t))]
        values_d = [-float(k) + (0.45 if (t + k) % 2 == 0 else 0.0)
                    for t in range(len(stamps_t))]
        obs_c.extend(_rows(stamps_t, values_c, entity_id=entity))
        obs_d.extend(_rows(stamps_t, values_d, entity_id=entity))
    seed("demo:sen:churn-create", {
        "name": "Stable components, churning combination",
        "universe": _universe({"stable-a": obs_c, "stable-b": obs_d}),
        "combination": {"mode": "equal_weight"},
        "prices": price_rows,
        "analysis": {"horizons": [1], "entry_lags": [0],
                     "bucket": {"bucket_count": 2,
                                "scope": "per_timestamp",
                                "minimum_per_bucket": 1}},
        "description": ("Each component's own ranking is stable, but "
                        "their sum alternates which entities lead, so "
                        "the combination's top bucket flips every "
                        "rebalance: combining can CREATE turnover as "
                        "well as remove it."),
    }, note="combination turnover exceeds component turnover")

    # 18. Training-versus-held-out difference.
    validation_id = validation_store.run_demo_key_id(
        UPSTREAM_VALIDATION_KEY)
    if validation_id is not None:
        vrun = validation_store.get_run(validation_id)
        splits = validation_store.list_splits(validation_id)
        sample_stamps = [s["prediction_time"] for s in
                         (vrun or {}).get("samples", [])
                         if s.get("prediction_time")]
        if vrun and splits and len(sample_stamps) >= 20:
            m = len(sample_stamps)
            vbase = [_s(i) + i * 1e-6 for i in range(m)]
            seed("demo:sen:held-out", {
                "name": "Training versus held-out (stored split)",
                "universe": _universe({
                    "val-a": _rows(sample_stamps, vbase),
                    "val-b": _rows(sample_stamps,
                                   [_a(i) + i * 1e-6 for i in range(m)]),
                }),
                "prices": [
                    {"entity_id": "aggregate", "timestamp": s,
                     "close": p["close"]}
                    for s, p in zip(sample_stamps, _prices_from_returns(
                        sample_stamps,
                        [0.01 * vbase[i] + 0.3 * _e(i)
                         for i in range(m - 1)]))],
                "analysis": {"horizons": [1], "entry_lags": [0]},
                "validation_run_id": validation_id,
                "validation_split_label": splits[0]["split_label"],
                "description": (
                    "Training, held-out and full-sample combination "
                    "diagnostics are reported separately on the stored "
                    "Phase 52 split; supplied weights stay fixed and "
                    "nothing is refitted on held-out data."),
            }, note="train/held-out separation on a stored split")

    # 19. Regime-dependent similarity shift.
    regime_id = regime_store.run_demo_key_id(UPSTREAM_REGIME_KEY)
    if regime_id is not None:
        rrun = regime_store.get_run(regime_id)
        definition = next(
            (d for d in regime_store.list_definitions(rrun["id"])
             if d["definition_id"] == UPSTREAM_REGIME_DEFINITION), None)
        regime_stamps = (rrun.get("timestamps") or [])[30:90]
        if definition and len(regime_stamps) >= 40:
            label_by_stamp = dict(zip(rrun["timestamps"],
                                      definition["assignments"]))
            rbase = [_s(i) + i * 1e-6 for i in range(len(regime_stamps))]
            flipped = [v if str(label_by_stamp.get(s)) == "low" else -v
                       for v, s in zip(rbase, regime_stamps)]
            seed("demo:sen:regime-shift", {
                "name": "Regime-dependent similarity shift",
                "universe": _universe({
                    "reg-a": _rows(regime_stamps, rbase),
                    "reg-b": _rows(regime_stamps, flipped),
                }),
                "regime_run_id": regime_id,
                "regime_definition_id": UPSTREAM_REGIME_DEFINITION,
                "description": (
                    "reg-b equals reg-a inside the stored 'low' "
                    "volatility regime and its negative elsewhere, so "
                    "the two signals are similar only in particular "
                    "STORED regimes (never recomputed); rare regimes "
                    "stay withheld."),
            }, note="similarity flips sign across stored regimes")

    # 20. Horizon-dependent response shift.
    n_h = 60
    stamps_h = _stamps(n_h)
    hbase = [_s(i) + i * 1e-6 for i in range(n_h)]
    halt = [_a(i) + i * 1e-6 for i in range(n_h)]
    # The step return realises ONLY the slow signal, three steps late: a
    # horizon-1 outcome barely sees today's slow value, while a horizon-4
    # outcome window covers it — the measured association shifts with the
    # horizon by construction.
    h_returns = [0.03 * halt[max(0, i - 3)] + 0.05 * _e(i)
                 for i in range(n_h - 1)]
    seed("demo:sen:horizon-shift", {
        "name": "Horizon-dependent response shift",
        "universe": _universe({
            "fast-sig": _rows(stamps_h, hbase),
            "slow-sig": _rows(stamps_h, halt),
        }),
        "prices": _prices_from_returns(stamps_h, h_returns),
        "analysis": {"horizons": [1, 4], "entry_lags": [0]},
        "description": ("The step return realises the slow signal three "
                        "steps late, so the combination's measured "
                        "association differs sharply between horizon 1 "
                        "and horizon 4; no horizon is called best."),
    }, note="association differs across horizons, none called best")

    # 21. Factor-residualised comparison.
    factor_id = factor_store.run_demo_key_id(UPSTREAM_FACTOR_KEY)
    if factor_id is not None:
        periods = factor_store.list_periods(factor_id)
        period_starts = [p["period_start"] for p in periods]
        if len(period_starts) >= 20:
            m = len(period_starts)
            fbase = [_s(i) + i * 1e-6 for i in range(m)]
            seed("demo:sen:factor-residual", {
                "name": "Raw versus factor-residual outcome comparison",
                "universe": _universe({
                    "fac-a": _rows(period_starts, fbase),
                    "fac-b": _rows(period_starts,
                                   [_a(i) + i * 1e-6 for i in range(m)]),
                }),
                "prices": [
                    {"entity_id": "aggregate", "timestamp": s,
                     "close": p["close"]}
                    for s, p in zip(period_starts, _prices_from_returns(
                        period_starts,
                        [0.01 * fbase[i] + 0.3 * _e(i)
                         for i in range(m - 1)]))],
                "analysis": {"horizons": [1], "entry_lags": [0]},
                "factor_run_id": factor_id,
                "description": (
                    "The combined score's outcomes are compared against "
                    "the linked Phase 59 run's stored residuals "
                    "(read-only, exact horizon coverage); raw and "
                    "residual scopes stay separate rows, no residual "
                    "association is called alpha, and signal-value "
                    "residualisation is deferred because no stored "
                    "residual signal series exists."),
            }, note="raw vs residual outcome scopes side by side")

    # 22. Cost-linked neutral reference.
    cost_id = cost_store.run_demo_key_id(UPSTREAM_COST_KEY)
    if cost_id is not None:
        obs_cost_a: List[Dict[str, Any]] = []
        obs_cost_b: List[Dict[str, Any]] = []
        price_rows_cost: List[Dict[str, Any]] = []
        stamps_c = _stamps(20)
        for k, entity in enumerate(entities):
            values_a = [float((t + k) % 5) + k * 1e-3
                        for t in range(len(stamps_c))]
            values_b = [float((t + 2 * k) % 5) - k * 1e-3
                        for t in range(len(stamps_c))]
            obs_cost_a.extend(_rows(stamps_c, values_a, entity_id=entity))
            obs_cost_b.extend(_rows(stamps_c, values_b, entity_id=entity))
            price_rows_cost.extend(_prices_from_returns(
                stamps_c, [0.0001 * ((t + k) % 5)
                           for t in range(len(stamps_c) - 1)],
                entity_id=entity))
        seed("demo:sen:cost-linked", {
            "name": "Cost-linked combination reference",
            "universe": _universe({"cost-a": obs_cost_a,
                                   "cost-b": obs_cost_b}),
            "prices": price_rows_cost,
            "analysis": {"horizons": [1], "entry_lags": [0],
                         "bucket": {"bucket_count": 2,
                                    "scope": "per_timestamp",
                                    "minimum_per_bucket": 1},
                         "reference_notional": 1_000_000},
            "cost_diagnostic_run_id": cost_id,
            "description": (
                "The linked Phase 55 model (pinned by fingerprint, "
                "read-only) prices the combination's reference turnover; "
                "only notional-proportional components are computable, "
                "gross and cost-adjusted stay separate columns, and "
                "missing cost inputs stay unavailable — never zero."),
        }, note="pinned cost model, gross vs cost-adjusted separate")

    # 23. Rank-deficient similarity matrix.
    third = [(base[i] + _a(i)) / 2.0 for i in range(n)]
    seed("demo:sen:rank-deficient", {
        "name": "Rank-deficient similarity matrix",
        "universe": _universe({
            "lin-a": _rows(stamps, base),
            "lin-b": _rows(stamps, [_a(i) for i in range(n)]),
            "lin-c": _rows(stamps, third),
        }),
        "similarity": {"matrix_method": "pearson",
                       "correlation_methods": ["pearson", "spearman"]},
        "description": ("lin-c = (lin-a + lin-b) / 2 exactly, so the "
                        "Pearson correlation matrix is rank deficient: "
                        "the rank warning is visible, the condition "
                        "number is unavailable rather than infinite, and "
                        "nothing is silently repaired."),
    }, note="exact linear dependence -> rank warning")

    # 24. Eligible baseline.
    seed("demo:sen:baseline-candidate", {
        "name": "Baseline candidate (point-in-time, complete)",
        "universe": _universe({
            "base-a": _rows(stamps, base),
            "base-b": _rows(stamps, [_a(i) + i * 1e-6 for i in range(n)]),
        }),
        "prices": prices,
        "analysis": {"horizons": [1], "entry_lags": [0],
                     "multiple_testing": {"methods": ["holm", "bh"],
                                          "alpha": 0.05},
                     "bootstrap": {"method": "timestamp",
                                   "statistics":
                                       ["mean_absolute_correlation",
                                        "effective_signal_count"],
                                   "seed": 61, "resamples": 200}},
        "description": ("Explicit availability on every observation, "
                        "full coverage and a reconciled combination: the "
                        "only kind of run this lab accepts as a "
                        "comparison baseline — never chosen by IC, "
                        "spread, cost, effective count or turnover."),
    }, baseline=True, experiment=True,
        note="eligible baseline with adjustment and bootstrap")

    return {"created": created > 0, "created_count": created,
            "skipped_count": skipped, "run_ids": run_ids, "notes": notes}


__all__ = ["seed_demo_signal_ensemble", "ALT_CYCLE"]
