"""Explicit deterministic educational inputs. Never seeded at startup."""

from copy import deepcopy
from datetime import datetime, timedelta

from app.experiment_registry.fingerprints import sha256_hex
from . import service, store


def payload(name="Identical streams", values=None, basis="gross"):
    a = [-0.02, 0.01, 0.03, -0.01, 0.02, -0.03, 0.04, 0.0] * 5
    series = values or {"a": a, "b": a}
    n = len(next(iter(series.values())))
    dates = [(datetime(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(n+1)]
    definitions, observations = [], []
    for key, returns in series.items():
        definitions.append({"strategy_id": key, "strategy_name": f"Strategy {key.upper()}",
                            "source_type": "supplied", "source_fingerprint": sha256_hex(returns),
                            "configuration_fingerprint": sha256_hex({"demo": key}),
                            "dataset_identity": "phase64_deterministic_returns_v1",
                            "return_convention": "simple_arithmetic", "gross_or_net": basis,
                            "frequency": "daily", "currency": "USD", "leverage_convention": "already_in_returns",
                            "exposure_convention": "strategy_return_weight",
                            "availability_policy": "outcome_at_or_after_period_end",
                            "configuration_available_at": dates[0], "observation_start": dates[0], "observation_end": dates[-1]})
        observations.extend({"strategy_id": key, "period_start": dates[i], "period_end": dates[i+1],
                             "return_value": v, "gross_or_net": basis, "information_available_at": dates[i+1],
                             "source_observation_id": f"p{i:03d}"} for i, v in enumerate(returns))
    return {"name": name, "description": "Deterministic educational fixture, not market performance.",
            "definitions": definitions, "observations": observations, "weights_available_at": dates[0]}


def linked_fixture():
    """Creates only this phase's deterministic records through existing services."""
    from app.regime_diagnostics import service as rs, store as rst
    from app.model_validation import service as vs, store as vst

    data = payload()
    obs = [r for r in data["observations"] if r["strategy_id"] == "a"]
    key = "phase64_regime_reference_v1"
    rid = rst.run_demo_key_id(key)
    if rid is None:
        r = rs.create_run({"name": "Phase 64 stored regime reference", "frequency": "daily",
                           "timestamps": [r["period_start"] for r in obs],
                           "candidates": [{"candidate_id": "reference", "outcomes": [r["return_value"] for r in obs]}],
                           "definitions": [{"definition_id": "halves", "dimension": "categorical",
                                            "labels_supplied": ["first"]*20 + ["second"]*20,
                                            "provenance": {"causality": "trailing", "source": "phase64_fixed_demo"}}]}, demo_key=key)
        rid = r["id"]
        rs.execute_run(rid)
    key = "phase64_validation_reference_v1"
    vid = vst.run_demo_key_id(key)
    if vid is None:
        r = vs.create_run({"name": "Phase 64 stored validation reference", "method": "purged_kfold",
                           "configuration": {"n_folds": 2},
                           "samples": [{"sample_id": r["source_observation_id"], "prediction_time": r["period_start"],
                                        "evaluation_time": r["period_end"], "ret": r["return_value"]} for r in obs]}, demo_key=key)
        vid = r["id"]
        vs.execute_run(vid)
    return {"regime": {"run_id": rid, "definition_id": "halves"},
            "validation": {"run_id": vid, "split_label": vst.list_splits(vid)[0]["split_label"]}}


def seed():
    a = [-0.02, 0.01, 0.03, -0.01, 0.02, -0.03, 0.04, 0.0] * 5
    cases = [payload(), payload("Inverse streams", {"a": a, "b": [-v for v in a]}),
             payload("Constant stream", {"a": a, "b": [0.0]*40})]
    missing = payload("Missing periods", {"a": a, "b": a, "c": [-v for v in a]})
    missing["observations"] = [r for i, r in enumerate(missing["observations"]) if i not in (2, 43, 84)]
    missing["analysis"] = {"pairwise_alignment": "pairwise_complete"}
    cases.append(missing)
    # Shared losses with dissimilar gains illustrate why a single rho is incomplete.
    cases.append(payload("Joint losses and dissimilar gains", {"a": [-.03, .001, .02, .06]*10,
                                                              "b": [-.03, .06, .02, .001]*10}))
    cases.append(payload("Shifted drawdown timing", {"a": a, "b": [v+.015 for v in a]}))
    net = payload("Net costs already included", basis="net_of_strategy_costs")
    for r in net["observations"]:
        r.update(cost_return=0.001, turnover=0.5)
    cases.append(net)
    weighted = payload("Static weights and sensitivity", {"a": a, "b": [-v/2 for v in a]})
    weighted["policy"] = {"mode": "user_static", "weights": {"a": .75, "b": .25}, "initial_build": "zero_prior_weights"}
    weighted["scenarios"] = [{"label": "Equal reference", "policy": {"mode": "equal_weight"}},
                             {"label": "Explicit 25/75", "policy": {"mode": "user_static", "weights": {"a": .25, "b": .75}}}]
    cases.append(weighted)
    linked = payload("Stored regimes and held-out", {"a": a, "b": a[:20] + [-v for v in a[20:]]})
    linked.update(linked_fixture())
    cases.append(linked)
    invalid = payload("Invalid outcome timing")
    invalid["observations"][0]["information_available_at"] = invalid["observations"][0]["period_start"]
    cases.append(invalid)
    created, ids = 0, []
    for index, case in enumerate(cases):
        key = f"phase64_strategy_ensemble_v1_{index:02d}"
        run_id = store.demo_id(key)
        if run_id is None:
            run_id = service.create_run(deepcopy(case), demo_key=key)["id"]
            try:
                service.execute_run(run_id)
            except ValueError:
                if case["name"] != "Invalid outcome timing":
                    raise
            created += 1
        ids.append(run_id)
    return {"created_count": created, "skipped_count": len(cases)-created, "run_ids": ids}
