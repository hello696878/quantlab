"""
Deterministic, idempotent demo for the Portfolio Attribution Lab (17 cases).

The demo seeds its own small Phase 56 portfolio books through the Phase 56
PUBLIC service (new records only — no existing record is modified) so every
number here is hand-computable.  Each book repeats an exact two-period
return cycle and is restored to its target weights every period, so the
beginning-of-period weights are exactly the declared targets:

    period type A returns:  eq-a +2%, eq-b +4%, bd-a +1%, bd-b -1%
    period type B returns:  eq-a -1%, eq-b -2%, bd-a  0%, bd-b +2%

Worked example (balanced book 0.30/0.30/0.20/0.20 vs an equal-weight
benchmark, period type A):

    portfolio  0.30(0.02) + 0.30(0.04) + 0.20(0.01) + 0.20(-0.01) = 0.018
    benchmark  0.25(0.02) + 0.25(0.04) + 0.25(0.01) + 0.25(-0.01) = 0.015
    active                                                        = 0.003
    equity     Wp 0.60 Rp 0.030 | Wb 0.50 Rb 0.030
    bond       Wp 0.40 Rp 0.000 | Wb 0.50 Rb 0.000
    allocation (0.60-0.50)(0.030-0.015) + (0.40-0.50)(0.000-0.015) = 0.003
    selection / interaction                                        = 0

Demo keys make re-seeding a no-op; only the flagship creates an Experiment
Registry record.  Every case is an educational measurement — none is
evidence of alpha, skill, or a preferred portfolio or benchmark.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
from app.cost_diagnostics.store import run_demo_key_id as cost_demo_id
from app.portfolio_diagnostics import service as pd_service
from app.portfolio_diagnostics import store as pd_store
from app.portfolio_attribution import service, store

_BASE = datetime(2024, 3, 1)
N_OBS = 30                      # 29 periods; the book starts at index 3
FIRST_PERIOD_INDEX = 3

ASSETS = ("eq-a", "eq-b", "bd-a", "bd-b")
GROUPS = {"eq-a": "equity", "eq-b": "equity",
          "bd-a": "bond", "bd-b": "bond"}
CYCLE_A = {"eq-a": 0.02, "eq-b": 0.04, "bd-a": 0.01, "bd-b": -0.01}
CYCLE_B = {"eq-a": -0.01, "eq-b": -0.02, "bd-a": 0.0, "bd-b": 0.02}


def _timestamps(n: int = N_OBS) -> List[str]:
    return [(_BASE + timedelta(days=i)).isoformat() for i in range(n)]


def _returns(asset_id: str) -> List[float]:
    """The cycle is phased so the FIRST attribution period (index
    ``FIRST_PERIOD_INDEX``) is a type-A period — the worked example in the
    module docstring is exactly the first period a reader sees."""
    return [CYCLE_A[asset_id] if (t - FIRST_PERIOD_INDEX) % 2 == 0
            else CYCLE_B[asset_id] for t in range(N_OBS)]


def _universe() -> List[Dict[str, Any]]:
    return [{"asset_id": a, "name": a, "asset_type": "index",
             "group": GROUPS[a], "returns": _returns(a)} for a in ASSETS]


def _book_payload(name: str, description: str, weights: Dict[str, float],
                  **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "name": name, "description": description,
        "method": "user_supplied", "frequency": "daily",
        "timestamps": _timestamps(), "assets": _universe(),
        # trailing window with lag >= 1; weights are restored every period so
        # each period begins at exactly the declared targets
        "estimation": {"mode": "rolling", "lookback": 3, "lag": 1},
        "rebalance": {"kind": "every_n", "every_n": 1,
                      "initial_turnover_policy": "zero_book"},
        "weights": weights,
        "weight_provenance": {"basis": "causal_rolling"},
        "normalization": "none",
    }
    payload.update(extra)
    return payload


def _window() -> Dict[str, str]:
    stamps = _timestamps()
    return {"observation_start": stamps[FIRST_PERIOD_INDEX],
            "observation_end": stamps[N_OBS - 1]}


def _benchmark(weights: Dict[str, float], *, benchmark_id: str, name: str,
               kind: str = "fixed_weights",
               asset_ids: Optional[List[str]] = None,
               groups: Optional[Dict[str, str]] = None,
               returns: Optional[Dict[str, List[float]]] = None
               ) -> Dict[str, Any]:
    ids = asset_ids or list(ASSETS)
    definition: Dict[str, Any] = {
        "benchmark_id": benchmark_id, "name": name, "kind": kind,
        "source": "demo_fixture", "asset_ids": ids,
        "weights": [weights[a] for a in ids],
    }
    if groups:
        definition["groups"] = groups
    if returns:
        definition["returns"] = returns
    return definition


EQUAL_WEIGHTS = {a: 0.25 for a in ASSETS}
BALANCED_WEIGHTS = {"eq-a": 0.30, "eq-b": 0.30, "bd-a": 0.20, "bd-b": 0.20}
SELECTION_WEIGHTS = {"eq-a": 0.0, "eq-b": 0.60, "bd-a": 0.20, "bd-b": 0.20}
INTERACTION_WEIGHTS = {"eq-a": 0.0, "eq-b": 0.70, "bd-a": 0.15, "bd-b": 0.15}
CONCENTRATED_WEIGHTS = {"eq-a": 0.85, "eq-b": 0.05, "bd-a": 0.05, "bd-b": 0.05}
LONG_SHORT_WEIGHTS = {"eq-a": 0.80, "eq-b": 0.40, "bd-a": -0.20, "bd-b": 0.0}


def seed_demo_portfolio_attribution() -> Dict[str, Any]:
    seed_demo_cost_diagnostics()   # idempotent; cascades upstream demos

    created = 0
    skipped = 0
    run_ids: List[int] = []
    notes: List[str] = []

    def book(key: str, payload: Dict[str, Any]) -> int:
        """Seed a Phase 56 book through its public service (new record)."""
        existing = pd_store.run_demo_key_id(key)
        if existing is not None:
            return existing
        run = pd_service.create_run(payload, demo_key=key)
        pd_service.execute_run(run["id"])
        return run["id"]

    def seed(key: str, payload: Dict[str, Any], *, baseline: bool = False,
             experiment: bool = False, note: str = "") -> None:
        nonlocal created, skipped
        existing = store.run_demo_key_id(key)
        if existing is not None:
            skipped += 1
            run_ids.append(existing)
            return
        run = service.create_run(payload, demo_key=key)
        service.execute_run(run["id"], create_experiment=experiment)
        if baseline:
            service.mark_baseline(run["id"])
        created += 1
        run_ids.append(run["id"])
        if note:
            notes.append(note)

    balanced = book("demo:pd:attr-balanced", _book_payload(
        "Attribution demo book — balanced",
        "A hand-computable four-asset book (equity 60% / bond 40%) restored "
        "to its target weights every period, used by the attribution demo.",
        BALANCED_WEIGHTS))
    selection_book = book("demo:pd:attr-selection", _book_payload(
        "Attribution demo book — within-group selection",
        "The same universe held only through eq-b inside the equity group, "
        "so the equity group return differs from the benchmark's.",
        SELECTION_WEIGHTS))
    interaction_book = book("demo:pd:attr-interaction", _book_payload(
        "Attribution demo book — interaction",
        "Equity overweight AND a different within-equity mix, so the "
        "interaction term is non-zero.",
        INTERACTION_WEIGHTS))
    concentrated_book = book("demo:pd:attr-concentrated", _book_payload(
        "Attribution demo book — concentrated",
        "85% of the book in a single asset, for the contribution "
        "concentration measurement.",
        CONCENTRATED_WEIGHTS))
    long_short_book = book("demo:pd:attr-long-short", _book_payload(
        "Attribution demo book — long/short",
        "A long/short book with a negative bond weight, for the documented "
        "long-short group-return semantics.",
        LONG_SHORT_WEIGHTS))
    costed_book = book("demo:pd:attr-costed", _book_payload(
        "Attribution demo book — with linked costs",
        "The balanced book with a linked Phase 55 cost model, so each "
        "rebalance carries a stored cost estimate.",
        BALANCED_WEIGHTS,
        cost_diagnostic_run_id=cost_demo_id("demo:cd:complete-costs"),
        cost_notional=1_000_000.0))

    window = _window()

    # 1 — flagship: allocation-driven active return, fully reconciled
    seed("demo:pa:flagship-allocation", {
        "name": "Flagship allocation attribution vs an equal-weight benchmark",
        "description": (
            "The balanced book (equity 60/bond 40) against an explicitly "
            "declared equal-weight benchmark. Every period: portfolio 1.80%, "
            "benchmark 1.50%, active 0.30%, entirely allocation — selection "
            "and interaction are exactly zero because the within-group mixes "
            "match. Brinson-Fachler effects reconcile with active return to "
            "the last digit."),
        "portfolio_run_id": balanced,
        "attribution_method": "brinson",
        "brinson_variant": "brinson_fachler",
        "linking_method": "arithmetic",
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS,
                                benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    }, baseline=True, experiment=True,
        note="flagship allocation case (baseline + experiment record)")

    # 2 — identical benchmark: exactly zero active return and zero effects
    seed("demo:pa:zero-active", {
        "name": "Identical benchmark — zero active return",
        "description": (
            "The benchmark declares the same weights as the portfolio, so "
            "active return and every Brinson effect are exactly zero and "
            "tracking error is zero (which leaves the information ratio "
            "honestly unavailable rather than infinite)."),
        "portfolio_run_id": balanced,
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(BALANCED_WEIGHTS,
                                benchmark_id="same-as-portfolio",
                                name="Same-weights benchmark"),
        **window,
    })

    # 3 — selection effect
    seed("demo:pa:selection", {
        "name": "Within-group selection effect",
        "description": (
            "Equity held only through eq-b (the stronger equity asset in the "
            "type-A period) at the benchmark's group weight, so the effect "
            "is selection rather than allocation."),
        "portfolio_run_id": selection_book,
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 4 — interaction effect
    seed("demo:pa:interaction", {
        "name": "Non-zero interaction effect",
        "description": (
            "The equity group is BOTH overweight and differently composed, "
            "so the interaction term — the part attributable to neither "
            "decision alone — is non-zero and reported separately."),
        "portfolio_run_id": interaction_book,
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 5 — portfolio-only group (benchmark holds no bonds)
    seed("demo:pa:portfolio-only-group", {
        "name": "Portfolio-only group (benchmark holds no bonds)",
        "description": (
            "The benchmark contains equities only, so the bond group exists "
            "on the portfolio side alone: its benchmark weight is zero and "
            "its benchmark return is unavailable, so the terms that need it "
            "are unavailable and the omission is visible in the residual."),
        "portfolio_run_id": balanced,
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark({"eq-a": 0.5, "eq-b": 0.5},
                                benchmark_id="equity-only",
                                name="Equity-only benchmark",
                                asset_ids=["eq-a", "eq-b"]),
        **window,
    })

    # 6 — benchmark-only group with explicit returns
    seed("demo:pa:benchmark-only-group", {
        "name": "Benchmark-only group (an asset the portfolio never holds)",
        "description": (
            "The benchmark adds a commodity asset the portfolio does not "
            "hold, with EXPLICIT returns and an EXPLICIT group (never "
            "inferred from its name). Its portfolio weight is zero, so the "
            "portfolio group return is unavailable and the affected terms "
            "are reported unavailable."),
        "portfolio_run_id": balanced,
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(
            {"eq-a": 0.25, "eq-b": 0.25, "bd-a": 0.2, "bd-b": 0.2,
             "cm-a": 0.10},
            benchmark_id="with-commodity",
            name="Equal-weight plus a commodity sleeve",
            asset_ids=[*ASSETS, "cm-a"],
            groups={"cm-a": "commodity"},
            returns={"cm-a": [0.005] * (N_OBS - 1 - FIRST_PERIOD_INDEX)}),
        **window,
    })

    # 7 — zero group weight on both sides
    seed("demo:pa:zero-group-weight", {
        "name": "Zero group weight on both sides",
        "description": (
            "Both books hold zero bond weight, so the bond group return is "
            "unavailable on both sides — a group with no capital has no "
            "weighted return and one is never fabricated from its "
            "constituents' returns."),
        "portfolio_run_id": book("demo:pd:attr-equity-only", _book_payload(
            "Attribution demo book — equity only",
            "Equity-only book for the zero-group-weight edge case.",
            {"eq-a": 0.5, "eq-b": 0.5, "bd-a": 0.0, "bd-b": 0.0})),
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(
            {"eq-a": 0.5, "eq-b": 0.5, "bd-a": 0.0, "bd-b": 0.0},
            benchmark_id="equity-only-with-empty-bond",
            name="Equity-only benchmark carrying an empty bond sleeve"),
        **window,
    })

    # 8 — arithmetic linking residual vs the compounded active return
    seed("demo:pa:arithmetic-linking", {
        "name": "Arithmetic linking — the compounding gap made visible",
        "description": (
            "Single-period effects are summed. The sum reconciles with the "
            "SUMMED active return exactly, but not with the compounded "
            "(geometric) active return; that gap is reported as an explicit "
            "arithmetic-versus-geometric difference rather than hidden."),
        "portfolio_run_id": balanced,
        "linking_method": "arithmetic",
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 9 — Carino linking
    seed("demo:pa:carino-linking", {
        "name": "Carino linking — effects reconciled with geometric active return",
        "description": (
            "The same effects linked by Carino logarithmic smoothing: the "
            "linked effects reconcile with the compounded active return "
            "within tolerance, and the per-period smoothing factors are "
            "exported. The exact x=y limit 1/(1+x) is used instead of an "
            "epsilon guard."),
        "portfolio_run_id": balanced,
        "linking_method": "carino",
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 10 — gross vs cost-adjusted
    seed("demo:pa:gross-vs-net", {
        "name": "Gross versus cost-adjusted attribution",
        "description": (
            "The same book with a linked Phase 55 cost model: each period's "
            "market contribution is kept strictly separate from its "
            "transaction cost, and the net figure states the costed basis. "
            "Components Phase 55 cannot estimate for weight turnover stay "
            "unavailable rather than zero."),
        "portfolio_run_id": costed_book,
        "cost_policy": "stored_rebalance_costs",
        "cost_diagnostic_run_id": cost_demo_id("demo:cd:complete-costs"),
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 11 — contribution concentration
    seed("demo:pa:concentration", {
        "name": "Contribution concentration in a single asset",
        "description": (
            "85% of the book sits in one asset, so the absolute-contribution "
            "Herfindahl is high and the effective number of contributors is "
            "low. That is a measurement — not evidence of poor "
            "diversification or overfitting."),
        "portfolio_run_id": concentrated_book,
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 12 — long/short contribution semantics
    seed("demo:pa:long-short", {
        "name": "Long/short book — documented group-return semantics",
        "description": (
            "A negative bond weight makes the bond group's weighted-return "
            "ratio sign-unstable, so it is reported with an explicit "
            "negative-weight state rather than silently divided, and the "
            "group's return is not compared directly with a long group's."),
        "portfolio_run_id": long_short_book,
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 13 — contribution-only method (no benchmark configured)
    seed("demo:pa:contribution-only", {
        "name": "Contribution-only attribution (no benchmark)",
        "description": (
            "No benchmark is configured, so benchmark-relative measurements "
            "are unavailable — a benchmark is never selected automatically. "
            "Asset and group contributions still reconcile exactly with the "
            "portfolio market return."),
        "portfolio_run_id": balanced,
        "attribution_method": "contribution_only",
        "policy": {"return_frequency": "daily"},
        **window,
    })

    # 14 — buy-and-hold benchmark that drifts
    seed("demo:pa:buy-and-hold-benchmark", {
        "name": "Buy-and-hold benchmark (drifting weights)",
        "description": (
            "The benchmark's declared weights drift with its own returns "
            "instead of being restored each period, by the same recursion "
            "the portfolio uses — an explicitly different, documented "
            "benchmark timing behaviour."),
        "portfolio_run_id": balanced,
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight-bh",
                                name="Equal-weight buy-and-hold benchmark",
                                kind="buy_and_hold"),
        **window,
    })

    # 15 — invalid end-of-period weight timing
    seed("demo:pa:invalid-timing", {
        "name": "Invalid end-of-period weight timing",
        "description": (
            "End-of-period weights are declared. A weight formed at the END "
            "of a period already embeds that period's return, so the run is "
            "labelled invalid, its results are descriptive only, and it can "
            "never become a baseline."),
        "portfolio_run_id": balanced,
        "policy": {"return_frequency": "daily",
                   "weight_timing_policy": "end_of_period"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 16 — unspecified frequency: annualized figures withheld
    seed("demo:pa:unspecified-frequency", {
        "name": "Unspecified frequency — annualized figures withheld",
        "description": (
            "With the return frequency declared 'unspecified', the per-period "
            "tracking error is still reported but the ANNUALIZED tracking "
            "error stays unavailable: a periods-per-year factor is never "
            "assumed."),
        "portfolio_run_id": balanced,
        "policy": {"return_frequency": "unspecified"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    # 17 — Brinson-Hood-Beebower variant side by side
    seed("demo:pa:bhb-variant", {
        "name": "Brinson-Hood-Beebower variant",
        "description": (
            "The same book and benchmark decomposed with the BHB allocation "
            "convention (Wp-Wb) x Rb instead of Brinson-Fachler's "
            "(Wp-Wb) x (Rb - Rb_total). Both decompose the same active "
            "return; only the allocation benchmark differs."),
        "portfolio_run_id": balanced,
        "brinson_variant": "brinson_hood_beebower",
        "policy": {"return_frequency": "daily"},
        "benchmark": _benchmark(EQUAL_WEIGHTS, benchmark_id="equal-weight",
                                name="Equal-weight four-asset benchmark"),
        **window,
    })

    return {"created": created > 0, "created_count": created,
            "skipped_count": skipped, "run_ids": run_ids, "notes": notes}


__all__ = ["seed_demo_portfolio_attribution", "ASSETS", "GROUPS",
           "CYCLE_A", "CYCLE_B", "BALANCED_WEIGHTS", "EQUAL_WEIGHTS",
           "N_OBS", "FIRST_PERIOD_INDEX"]
