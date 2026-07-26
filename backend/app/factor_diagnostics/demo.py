"""
Deterministic Factor Diagnostics demo fixture (v1).

Twenty idempotent cases over SYNTHETIC, generic series — no downloaded,
scraped or real financial data, and no network access of any kind.  Every
relationship is hand-computable:

    FACTOR_A cycle  [ 0.010, -0.005,  0.020,  0.000, -0.010,  0.015 ]
    FACTOR_B cycle  [ 0.004,  0.008, -0.006,  0.012, -0.002,  0.006 ]
    RESIDUAL cycle  [-0.00006, -0.00044, 0.0, 0.00034, 0.00016, 0.0 ]

The residual cycle is orthogonal to the constant AND to both factors over
one full cycle:

    sum(RESIDUAL) = 0
    sum(FACTOR_A x RESIDUAL) = 0
    sum(FACTOR_B x RESIDUAL) = 0

so over a whole number of cycles ordinary least squares recovers the
generating intercept and slopes EXACTLY while still leaving a non-zero
residual.  That is what makes the standard errors, t-statistics, confidence
intervals and p-values of the "intercept and residual" case verifiable by
hand.

Upstream demos (Regime, Model Validation, Portfolio Attribution and
Portfolio Stress) are seeded first through their own idempotent loaders and
are then read READ-ONLY; nothing upstream is modified.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

from app.factor_diagnostics import service
from app.factor_diagnostics import store
from app.model_validation import store as validation_store
from app.model_validation.demo import seed_demo_validation
from app.portfolio_attribution import store as attribution_store
from app.portfolio_attribution.demo import seed_demo_portfolio_attribution
from app.portfolio_stress import store as stress_store
from app.portfolio_stress.demo import seed_demo_portfolio_stress
from app.regime_diagnostics import store as regime_store
from app.regime_diagnostics.demo import seed_demo_regime_diagnostics

BASE_START = date(2024, 6, 3)
BASE_PERIODS = 36
FACTOR_HISTORY = 3          # observations supplied BEFORE the target window

FACTOR_A = (0.010, -0.005, 0.020, 0.000, -0.010, 0.015)
FACTOR_B = (0.004, 0.008, -0.006, 0.012, -0.002, 0.006)
RESIDUAL = (-0.00006, -0.00044, 0.0, 0.00034, 0.00016, 0.0)
RATE_LEVEL_STEP = (0.0002, -0.0001, 0.0003, 0.0000, -0.0002, 0.0001)

UPSTREAM_REGIME_KEY = "demo:rd:volatility-trend"
UPSTREAM_REGIME_DEFINITION = "vol"
UPSTREAM_VALIDATION_KEY = "demo:mv:baseline-candidate"
UPSTREAM_ATTRIBUTION_KEY = "demo:pa:flagship-allocation"
UPSTREAM_STRESS_KEY = "demo:ps:flagship-group-shock"


def _stamp(day: date) -> str:
    return f"{day.isoformat()}T00:00:00"


def _grid(count: int, start: date = BASE_START, *,
          history: int = 0) -> List[str]:
    first = start - timedelta(days=history)
    return [_stamp(first + timedelta(days=i)) for i in range(count + history)]


def _cycle(values: Sequence[float], index: int) -> float:
    return float(values[index % len(values)])


def _factor_a(index: int) -> float:
    return _cycle(FACTOR_A, index)


def _factor_b(index: int) -> float:
    return _cycle(FACTOR_B, index)


def _residual(index: int) -> float:
    return _cycle(RESIDUAL, index)


def _observations(stamps: Sequence[str], values: Sequence[float], *,
                  prefix: str, available_at: Optional[Sequence[str]] = None,
                  quality: str = "observed") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, stamp in enumerate(stamps):
        row: Dict[str, Any] = {
            "observation_id": f"{prefix}-{index:03d}",
            "source_timestamp": stamp,
            "value": float(values[index]),
            "quality_state": quality,
        }
        if available_at is not None:
            row["available_at"] = available_at[index]
        rows.append(row)
    return rows


def _factor(factor_id: str, *, name: str, category: str, unit: str,
            transformation: str, observations: List[Dict[str, Any]],
            lag: int = 0, availability: str = "same_timestamp",
            description: str = "", frequency: str = "daily",
            **extra: Any) -> Dict[str, Any]:
    payload = {
        "factor_id": factor_id, "name": name, "category": category,
        "source": "synthetic demo fixture (locally generated)",
        "unit": unit, "frequency": frequency,
        "transformation": transformation, "lag": lag,
        "availability_policy": availability,
        "description": description,
        "observations": observations,
    }
    payload.update(extra)
    return payload


def _simple_factors(stamps: Sequence[str], *, lag: int = 0,
                    availability: str = "same_timestamp",
                    include_b: bool = True) -> List[Dict[str, Any]]:
    a_values = [_factor_a(i) for i in range(len(stamps))]
    factors = [_factor(
        "factor_a", name="Factor A (synthetic style proxy)", category="style",
        unit="return_fraction", transformation="supplied_transformed",
        transformed_unit="return_fraction",
        observations=_observations(stamps, a_values, prefix="fa"),
        lag=lag, availability=availability,
        description="Deterministic six-period cycle supplied as a return.")]
    if include_b:
        b_values = [_factor_b(i) for i in range(len(stamps))]
        factors.append(_factor(
            "factor_b", name="Factor B (synthetic style proxy)",
            category="style", unit="return_fraction",
            transformation="supplied_transformed",
            transformed_unit="return_fraction",
            observations=_observations(stamps, b_values, prefix="fb"),
            lag=lag, availability=availability,
            description="Second deterministic cycle, offset from Factor A."))
    return factors


def _target(returns: Sequence[float], stamps: Sequence[str], *,
            target_type: str = "strategy_return",
            target_id: str = "demo-target") -> Dict[str, Any]:
    return {
        "target_id": target_id, "target_type": target_type,
        "source": "user_supplied", "return_convention": "simple",
        "frequency": "daily", "currency": "USD",
        "timestamps": list(stamps), "returns": [float(r) for r in returns],
        "description": "Synthetic demo return series (locally generated).",
    }


def seed_demo_factor_diagnostics() -> Dict[str, Any]:
    """Idempotent: loading twice creates nothing new."""
    seed_demo_regime_diagnostics()
    seed_demo_validation()
    seed_demo_portfolio_attribution()   # cascades the Phase 56 books
    seed_demo_portfolio_stress()

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
            # Cases 9 and similar exist to show an HONEST REFUSAL; the stored
            # failed run with its message is the demo.
            pass
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

    base_stamps = _grid(BASE_PERIODS, history=FACTOR_HISTORY)
    target_stamps = base_stamps[FACTOR_HISTORY:]
    offset = FACTOR_HISTORY  # factor index of the first target period

    # 1. Single-factor exact synthetic relationship: y = 0.6 * factor_a.
    seed("demo:fd:exact-single-factor", {
        "name": "Exact single-factor relationship (beta 0.60)",
        "description": (
            "y_t = 0.60 x factor_a_t exactly. The measured coefficient is "
            "0.600000 and R-squared is 1; because the residuals are exactly "
            "zero the classical standard errors collapse, so they are "
            "withheld rather than reported as zero with infinite "
            "t-statistics."),
        "analysis_mode": "time_series_regression",
        "target": _target([0.6 * _factor_a(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": _simple_factors(base_stamps, include_b=False),
        "policy": {"timing_policy": "contemporaneous"},
    }, note="exact single-factor case: coefficient 0.600000, R-squared 1")

    # 2. Two-factor known coefficients.
    seed("demo:fd:exact-two-factor", {
        "name": "Two known coefficients (1.50 and -0.50) with an intercept",
        "description": (
            "y_t = 0.002 + 1.50 x factor_a_t - 0.50 x factor_b_t exactly. "
            "The intercept is the mean unexplained return of THIS "
            "specification over THIS sample; it is not alpha."),
        "target": _target([0.002 + 1.5 * _factor_a(i + offset)
                           - 0.5 * _factor_b(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": _simple_factors(base_stamps),
        "policy": {"timing_policy": "contemporaneous"},
    }, note="exact two-factor case: 1.500000 / -0.500000, intercept 0.002")

    # 3. Non-zero intercept AND residual (statistics available).
    seed("demo:fd:intercept-and-residual", {
        "name": "Non-zero intercept and residual (statistics available)",
        "description": (
            "y_t = 0.001 + 0.80 x factor_a_t + e_t, where the six-period "
            "residual cycle is orthogonal to both the constant and factor_a, "
            "so least squares recovers 0.001 and 0.800000 exactly while the "
            "residuals stay non-zero. Standard errors, t-statistics, "
            "confidence intervals and p-values are therefore defined, and the "
            "Phase 53 multiple-testing corrections are applied to them."),
        "target": _target([0.001 + 0.8 * _factor_a(i + offset)
                           + _residual(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": _simple_factors(base_stamps),
        "policy": {"timing_policy": "contemporaneous",
                   "multiple_testing": {
                       "methods": ["bonferroni", "holm", "bh"],
                       "alpha": 0.05,
                       "family": "the two declared factors of this run"}},
        "sensitivity": [
            {"label": "shorter lookback (24)", "lookback": 24},
            {"label": "no intercept", "intercept_policy": "exclude"},
            {"label": "factor values x100", "factor_scale": 100.0},
            {"label": "ridge reference (lambda 0.001)",
             "ridge_lambda": 0.001},
            {"label": "factor_a only", "factor_subset": ["factor_a"]},
        ],
    }, experiment=True,
        note="intercept 0.001 and slope 0.800000 with live standard errors")

    # 4. Constant factor (intercept excluded so the design stays full rank).
    constant_values = [0.01] * len(base_stamps)
    seed("demo:fd:constant-factor", {
        "name": "Constant factor column (no intercept)",
        "description": (
            "A factor that never moves carries no cross-period information. "
            "With the intercept excluded the design is still full rank, so "
            "the run completes and the constant column is flagged rather "
            "than silently dropped. Its variance inflation factor is "
            "unavailable, and its correlation with anything is undefined."),
        "target": _target([0.001 + 0.8 * _factor_a(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": [
            _simple_factors(base_stamps, include_b=False)[0],
            _factor("factor_const", name="Constant factor",
                    category="custom_descriptive", unit="return_fraction",
                    transformation="supplied_transformed",
                    transformed_unit="return_fraction",
                    observations=_observations(base_stamps, constant_values,
                                               prefix="fc"),
                    description="Every observation equals 0.01."),
        ],
        "policy": {"timing_policy": "contemporaneous",
                   "intercept_policy": "exclude"},
    }, note="constant-column warning without rank deficiency")

    # 5. Duplicate factor -> rank deficient.
    duplicate = _simple_factors(base_stamps, include_b=False)[0]
    duplicate_copy = _factor(
        "factor_a_copy", name="Factor A (exact duplicate)", category="style",
        unit="return_fraction", transformation="supplied_transformed",
        transformed_unit="return_fraction",
        observations=_observations(base_stamps,
                                   [_factor_a(i)
                                    for i in range(len(base_stamps))],
                                   prefix="fad"),
        description="Byte-identical duplicate of factor_a.")
    seed("demo:fd:duplicate-factor", {
        "name": "Duplicate factor column (rank deficient)",
        "description": (
            "Two identical columns cannot be told apart by least squares. "
            "The run records the labelled minimum-norm solution, reports rank "
            "2 of 3, and withholds every standard error, t-statistic and "
            "p-value because the coefficients are not identified."),
        "target": _target([0.001 + 0.8 * _factor_a(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": [duplicate, duplicate_copy],
        "policy": {"timing_policy": "contemporaneous",
                   "rank_policy": "minimum_norm_descriptive"},
    }, note="rank 2 of 3 with duplicate columns")

    # 6. Rank-deficient design: factor_c = factor_a + factor_b.
    sum_values = [_factor_a(i) + _factor_b(i) for i in range(len(base_stamps))]
    seed("demo:fd:rank-deficient-sum", {
        "name": "Exact linear dependence (c = a + b)",
        "description": (
            "The third factor is the sum of the first two, so the design "
            "matrix is rank deficient by construction. The minimum-norm "
            "coefficients are labelled rank_deficient_descriptive, the "
            "variance inflation factors are unavailable rather than infinite, "
            "and this run can never become a comparison baseline."),
        "target": _target([0.001 + 0.8 * _factor_a(i + offset)
                           - 0.3 * _factor_b(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": _simple_factors(base_stamps) + [
            _factor("factor_c", name="Factor C = A + B",
                    category="custom_descriptive", unit="return_fraction",
                    transformation="supplied_transformed",
                    transformed_unit="return_fraction",
                    observations=_observations(base_stamps, sum_values,
                                               prefix="fsum"),
                    description="Exact sum of factor_a and factor_b."),
        ],
        "policy": {"timing_policy": "contemporaneous",
                   "rank_policy": "minimum_norm_descriptive"},
    }, note="exact linear dependence, minimum-norm solution")

    # 7. High condition number (near-duplicate factor).
    near = [_factor_a(i) + (0.0000001 if i % 2 == 0 else -0.0000001)
            for i in range(len(base_stamps))]
    seed("demo:fd:high-condition-number", {
        "name": "Near-collinear factors (high condition number)",
        "description": (
            "The second factor differs from the first by 1e-7 per "
            "observation. The design stays technically full rank, so "
            "coefficients and standard errors exist, but the condition number "
            "of the centred factor block is enormous: small input changes "
            "move the coefficients a lot. The flag is a neutral warning, not "
            "a universal rule."),
        "target": _target([0.001 + 0.8 * _factor_a(i + offset)
                           + _residual(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": [
            _simple_factors(base_stamps, include_b=False)[0],
            _factor("factor_a_near", name="Factor A (perturbed by 1e-7)",
                    category="style", unit="return_fraction",
                    transformation="supplied_transformed",
                    transformed_unit="return_fraction",
                    observations=_observations(base_stamps, near,
                                               prefix="fnear"),
                    description="factor_a with an alternating 1e-7 offset."),
        ],
        "policy": {"timing_policy": "contemporaneous"},
    }, note="condition-number warning with a full-rank design")

    # 8. Zero-variance target.
    seed("demo:fd:zero-variance-target", {
        "name": "Zero-variance target series",
        "description": (
            "Every target return equals 0.0010. The total sum of squares is "
            "zero, so R-squared is undefined and is reported as unavailable "
            "with a reason rather than as 0 or 1."),
        "target": _target([0.001] * BASE_PERIODS, target_stamps),
        "factors": _simple_factors(base_stamps, include_b=False),
        "policy": {"timing_policy": "contemporaneous"},
    }, note="R-squared unavailable for a constant target")

    # 9. Insufficient observations -> honest refusal.
    short_stamps = _grid(4, date(2024, 9, 2), history=FACTOR_HISTORY)
    short_target = short_stamps[FACTOR_HISTORY:]
    seed("demo:fd:insufficient-observations", {
        "name": "Insufficient observations (honest refusal)",
        "description": (
            "Four observations cannot identify three factor coefficients plus "
            "an intercept. The run FAILS with that statement instead of "
            "returning coefficients that are not identified; the stored error "
            "message is the result."),
        "target": _target([0.001, 0.002, -0.001, 0.0005], short_target),
        "factors": _simple_factors(short_stamps) + [
            _factor("factor_c", name="Factor C",
                    category="custom_descriptive", unit="return_fraction",
                    transformation="supplied_transformed",
                    transformed_unit="return_fraction",
                    observations=_observations(
                        short_stamps,
                        [_factor_a(i) + _factor_b(i)
                         for i in range(len(short_stamps))], prefix="fsum2"),
                    description="Third factor for the degrees-of-freedom "
                                "example."),
        ],
        "policy": {"timing_policy": "contemporaneous"},
    }, note="deliberate failure: 4 observations, 4 parameters")

    # 10. Lagged causal alignment.
    lagged_available = [s for s in base_stamps]
    seed("demo:fd:lagged-causal", {
        "name": "Lagged causal alignment (lag 1, availability verified)",
        "description": (
            "Every factor lags the target period by one period and declares "
            "an explicit availability timestamp that precedes the period it "
            "explains, so the timing claim is VERIFIED. This is a statement "
            "about information order only — it is not evidence of causality."),
        "target": _target([0.0008 + 0.9 * _factor_a(i + offset - 1)
                           + _residual(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": [
            _factor("factor_a", name="Factor A (lagged one period)",
                    category="style", unit="return_fraction",
                    transformation="supplied_transformed",
                    transformed_unit="return_fraction", lag=1,
                    availability="explicit_available_at",
                    observations=_observations(
                        base_stamps,
                        [_factor_a(i) for i in range(len(base_stamps))],
                        prefix="fa", available_at=lagged_available),
                    description="Known at its own timestamp, used one period "
                                "later."),
        ],
        "policy": {"timing_policy": "lagged_causal",
                   "estimation_scope": "rolling_trailing",
                   "rolling": {"window": 12, "step": 3}},
    }, note="verified_trailing_estimation with trailing rolling estimates")

    # 11. Contemporaneous descriptive.
    seed("demo:fd:contemporaneous-descriptive", {
        "name": "Contemporaneous alignment (descriptive only)",
        "description": (
            "The same factor carries the SAME period stamp as the target "
            "return. The measured association is descriptive and is never "
            "called ex-ante or predictive; only the timing differs from the "
            "lagged causal case."),
        "target": _target([0.0008 + 0.9 * _factor_a(i + offset)
                           + _residual(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": _simple_factors(base_stamps, include_b=False),
        "policy": {"timing_policy": "contemporaneous"},
    }, note="contemporaneous_descriptive integrity state")

    # 12. Future-looking INVALID alignment.
    seed("demo:fd:future-looking-invalid", {
        "name": "Future-looking alignment (declared INVALID)",
        "description": (
            "Factor values are taken one period AFTER the target period. The "
            "caller has to declare the timing policy invalid to get this at "
            "all; the run is marked invalid, warns loudly, and can never "
            "become a comparison baseline."),
        "target": _target([0.0008 + 0.9 * _factor_a(i + offset + 1)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": _simple_factors(base_stamps, include_b=False),
        "policy": {"timing_policy": "future_looking_invalid",
                   "lead_periods": 1},
    }, note="invalid integrity state, baseline refused")

    # 13. Rolling beta change.
    rolling_returns = [
        (0.5 if i < BASE_PERIODS // 2 else 1.5) * _factor_a(i + offset)
        + _residual(i + offset) for i in range(BASE_PERIODS)]
    seed("demo:fd:rolling-beta-change", {
        "name": "Rolling exposure change (0.50 then 1.50)",
        "description": (
            "The generating slope changes from 0.50 to 1.50 halfway through "
            "the sample. Trailing 12-observation windows show the change as "
            "it passes through them; each window reads only its own "
            "observations, so a later window can never rewrite an earlier "
            "one. A stable measured exposure is a property of this sample, "
            "not a permanent property of the factor."),
        "target": _target(rolling_returns, target_stamps),
        "factors": _simple_factors(base_stamps, include_b=False),
        "policy": {"timing_policy": "contemporaneous",
                   "rolling": {"window": 12, "step": 2}},
    }, note="rolling window shows the exposure change")

    # 14/17. Attribution-linked target + benchmark comparison.
    attribution_id = attribution_store.run_demo_key_id(
        UPSTREAM_ATTRIBUTION_KEY)
    if attribution_id is not None:
        periods = attribution_store.list_periods(attribution_id)
        attr_stamps = [p["period_start"] for p in periods]
        if len(attr_stamps) >= 8:
            attr_factor_stamps = attr_stamps
            a_values = [_factor_a(i) for i in range(len(attr_factor_stamps))]
            b_values = [_factor_b(i) for i in range(len(attr_factor_stamps))]
            attr_factors = [
                _factor("factor_a", name="Factor A (synthetic style proxy)",
                        category="style", unit="return_fraction",
                        transformation="supplied_transformed",
                        transformed_unit="return_fraction",
                        observations=_observations(attr_factor_stamps,
                                                   a_values, prefix="fa"),
                        description="Deterministic cycle on the attribution "
                                    "grid."),
                _factor("factor_b", name="Factor B (synthetic style proxy)",
                        category="style", unit="return_fraction",
                        transformation="supplied_transformed",
                        transformed_unit="return_fraction",
                        observations=_observations(attr_factor_stamps,
                                                   b_values, prefix="fb"),
                        description="Second deterministic cycle."),
            ]
            seed("demo:fd:benchmark-active-exposure", {
                "name": "Portfolio versus benchmark exposure (attribution "
                        "linked)",
                "description": (
                    "The portfolio market return of a stored Phase 58 "
                    "attribution run is regressed on the declared factors, "
                    "and the SAME specification is fitted to that run's "
                    "explicitly declared benchmark series. Active exposure is "
                    "portfolio exposure minus benchmark exposure — a measured "
                    "difference that is neither desirable nor undesirable. "
                    "The benchmark is never selected automatically."),
                "target": {
                    "target_id": "attribution-portfolio",
                    "target_type": "portfolio_return",
                    "source": "attribution_run",
                    "attribution_run_id": attribution_id,
                    "return_convention": "simple", "frequency": "daily",
                    "currency": "USD",
                    "description": "Stored Phase 58 portfolio market return.",
                },
                "factors": attr_factors,
                "benchmark_comparison": True,
                "policy": {"timing_policy": "contemporaneous"},
            }, note="portfolio/benchmark/active exposure comparison")

            seed("demo:fd:attribution-linked-active", {
                "name": "Active return decomposed by factor exposure",
                "description": (
                    "The same stored attribution run's ACTIVE return is "
                    "decomposed by factor exposure. This is a complementary "
                    "view to Brinson allocation and selection, not a "
                    "replacement: neither overwrites the other, transaction "
                    "cost stays inside the attribution lab, and the residual "
                    "here is not alpha."),
                "target": {
                    "target_id": "attribution-active",
                    "target_type": "active_return",
                    "source": "attribution_run",
                    "attribution_run_id": attribution_id,
                    "return_convention": "simple", "frequency": "daily",
                    "currency": "USD",
                    "description": "Stored Phase 58 active return.",
                },
                "factors": attr_factors,
                "policy": {"timing_policy": "contemporaneous"},
            }, note="attribution-linked factor decomposition of active return")

    # 15. Regime-linked exposure difference.
    regime_id = regime_store.run_demo_key_id(UPSTREAM_REGIME_KEY)
    if regime_id is not None:
        rrun = regime_store.get_run(regime_id)
        stamps = (rrun.get("timestamps") or [])[30:90]
        if len(stamps) >= 40:
            values = [_factor_a(i) for i in range(len(stamps))]
            returns = [
                (0.6 if i % 3 else 1.4) * values[i] + _residual(i)
                for i in range(len(stamps))]
            seed("demo:fd:regime-linked", {
                "name": "Exposure by STORED regime assignment",
                "description": (
                    "Periods are bucketed by the stored Phase 54 volatility "
                    "assignment; regimes are never recomputed here and their "
                    "fingerprints are pinned. A regime with fewer than "
                    f"{service.RARE_REGIME_MIN_OBSERVATIONS} observations has "
                    "its conditional fit withheld. Differences between "
                    "regimes are measurements, not structural or causal "
                    "claims."),
                "target": _target(returns, stamps),
                "factors": [
                    _factor("factor_a", name="Factor A (synthetic)",
                            category="style", unit="return_fraction",
                            transformation="supplied_transformed",
                            transformed_unit="return_fraction",
                            observations=_observations(stamps, values,
                                                       prefix="fa"),
                            description="Deterministic cycle on the regime "
                                        "grid."),
                ],
                "regime_run_id": regime_id,
                "regime_definition_id": UPSTREAM_REGIME_DEFINITION,
                "policy": {"timing_policy": "contemporaneous"},
            }, note="regime-conditional exposures from stored assignments")

    # 16. Stress-linked factor shock.
    stress_id = stress_store.run_demo_key_id(UPSTREAM_STRESS_KEY)
    if stress_id is not None:
        seed("demo:fd:stress-linked", {
            "name": "Exposure-implied factor shock (stress linked)",
            "description": (
                "Measured exposures are multiplied by EXPLICITLY supplied "
                "factor shocks expressed in each factor's transformed unit. "
                "Factor shocks are never inferred from the Phase 57 "
                "scenario's asset shocks, the stress records are read-only, "
                "no hedge or reallocation follows, and the number is not a "
                "prediction of realised loss."),
            "target": _target([0.001 + 0.8 * _factor_a(i + offset)
                               - 0.4 * _factor_b(i + offset)
                               + _residual(i + offset)
                               for i in range(BASE_PERIODS)], target_stamps),
            "factors": _simple_factors(base_stamps),
            "stress_run_id": stress_id,
            "stress_factor_shocks": {"factor_a": -0.05, "factor_b": 0.02},
            "policy": {"timing_policy": "contemporaneous"},
        }, note="exposure x supplied factor shock, no hedge implied")

    # 18. Held-out Model Validation evaluation.
    validation_id = validation_store.run_demo_key_id(UPSTREAM_VALIDATION_KEY)
    if validation_id is not None:
        vrun = validation_store.get_run(validation_id)
        splits = validation_store.list_splits(validation_id)
        sample_stamps = [s["prediction_time"] for s in (vrun or {}).get(
            "samples", []) if s.get("prediction_time")]
        if vrun and splits and len(sample_stamps) >= 20:
            values = [_factor_a(i) for i in range(len(sample_stamps))]
            returns = [0.0009 + 0.7 * values[i] + _residual(i)
                       for i in range(len(sample_stamps))]
            seed("demo:fd:held-out-validation", {
                "name": "Held-out evaluation on a stored validation split",
                "description": (
                    "Coefficients are fitted on the TRAINING observations of "
                    "a stored purged/embargoed split and applied unchanged to "
                    "the held-out observations. Purged and embargoed periods "
                    "belong to neither set. The held-out R-squared uses the "
                    "TRAINING mean in its denominator so no held-out "
                    "information enters the benchmark, and a negative value "
                    "is reported as measured."),
                "target": _target(returns, sample_stamps),
                "factors": [
                    _factor("factor_a", name="Factor A (synthetic)",
                            category="style", unit="return_fraction",
                            transformation="supplied_transformed",
                            transformed_unit="return_fraction",
                            observations=_observations(sample_stamps, values,
                                                       prefix="fa"),
                            description="Deterministic cycle on the "
                                        "validation sample grid."),
                ],
                "validation_run_id": validation_id,
                "validation_split_label": splits[0]["split_label"],
                "policy": {"timing_policy": "contemporaneous"},
            }, note="training-only fit with held-out metrics")

    # 19. Macro factor without a release timestamp.
    rate_levels: List[float] = []
    level = 0.0425
    for index in range(len(base_stamps)):
        level += _cycle(RATE_LEVEL_STEP, index)
        rate_levels.append(round(level, 8))
    seed("demo:fd:macro-missing-availability", {
        "name": "Macro factor with no release timestamp",
        "description": (
            "A synthetic policy-rate LEVEL is converted to a basis-point "
            "change (a rate_fraction difference multiplied by 10,000). The "
            "series declares no release timestamp, so the lab warns that "
            "availability is ASSUMED to equal the observation timestamp — an "
            "assumption about publication timing, not a measurement. No "
            "central-bank or economic data is downloaded anywhere in this "
            "lab."),
        "target": _target([0.001 - 0.0004 * (rate_levels[i + offset - 1]
                                              - rate_levels[i + offset - 2])
                           * 10000 + _residual(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": [
            _factor("macro_rate_change", name="Policy rate change (synthetic)",
                    category="macro", unit="rate_fraction",
                    transformation="basis_point_change", lag=1,
                    observations=_observations(base_stamps, rate_levels,
                                               prefix="mrc"),
                    description="Level series differenced into basis points, "
                                "used one period after it is observed."),
        ],
        "policy": {"timing_policy": "lagged_causal"},
    }, note="macro availability assumption surfaced as a warning")

    # 20. Valid baseline candidate.
    seed("demo:fd:baseline-candidate", {
        "name": "Baseline candidate (causal timing, full rank, reconciled)",
        "description": (
            "Lagged causal timing with verified availability, a full-rank "
            "design, complete results and an exactly reconciling "
            "decomposition — the only combination this lab accepts as a "
            "comparison baseline. A baseline is a comparison reference only: "
            "it is never chosen by R-squared, p-value or held-out "
            "performance, and it recommends nothing."),
        "target": _target([0.0012 + 1.1 * _factor_a(i + offset - 1)
                           - 0.4 * _factor_b(i + offset - 1)
                           + _residual(i + offset)
                           for i in range(BASE_PERIODS)], target_stamps),
        "factors": [
            _factor("factor_a", name="Factor A (lagged one period)",
                    category="style", unit="return_fraction",
                    transformation="supplied_transformed",
                    transformed_unit="return_fraction", lag=1,
                    availability="explicit_available_at",
                    observations=_observations(
                        base_stamps,
                        [_factor_a(i) for i in range(len(base_stamps))],
                        prefix="fa", available_at=list(base_stamps)),
                    description="Known at its own timestamp."),
            _factor("factor_b", name="Factor B (lagged one period)",
                    category="style", unit="return_fraction",
                    transformation="supplied_transformed",
                    transformed_unit="return_fraction", lag=1,
                    availability="explicit_available_at",
                    observations=_observations(
                        base_stamps,
                        [_factor_b(i) for i in range(len(base_stamps))],
                        prefix="fb", available_at=list(base_stamps)),
                    description="Known at its own timestamp."),
        ],
        "policy": {"timing_policy": "lagged_causal"},
    }, baseline=True, note="eligible baseline: verified timing, full rank")

    return {"created": created > 0, "created_count": created,
            "skipped_count": skipped, "run_ids": run_ids, "notes": notes}


__all__ = ["seed_demo_factor_diagnostics"]
