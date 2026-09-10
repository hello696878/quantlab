"""Validated run lifecycle with immutable inputs and pinned read-only links."""

import re

from app.experiment_registry.fingerprints import canonical_json, sha256_hex
from app.experiment_registry.integration import record_experiment
from . import SCHEMA_VERSION, core, links, store
from .models import RunCreate


class NotFoundError(ValueError):
    pass


class ConflictError(ValueError):
    pass


WARNINGS = [
    "Strategy returns are outcomes, not signals. No strategy or weight is selected.",
    "A weighted strategy-return reference is not a fully funded executable portfolio. Internal leverage is not applied again.",
    "Missing periods are omitted, not filled. Wealth compounds observed periods only; gaps are not cash returns.",
    "Volatility is per declared period, not annualized. Crypto and equity calendars are not interchangeable.",
    "Tail overlap and matrix concentration are descriptive; correlation does not prove diversification or independence.",
    "Contributions are arithmetic, not geometrically linked or causal. Cost completeness is limited to supplied declarations.",
    "Configuration/weight availability is caller-declared, not independently proven. No investment advice or execution.",
]
DEFERRED = {
    "walk_forward": "Only one explicit stored split is evaluated; multi-window stitching is deferred.",
    "factor": "No compatible strategy-return factor identity is persisted by the supported supplied source.",
    "stress": "No corresponding stored strategy-level stress identity; unrelated portfolio stress is not comparable.",
    "bootstrap": "Deferred: existing signal bootstrap resamples cross-sections, not this period-return contract.",
    "allocation_cost": "No executed rebalance notionals/drift modeled. Phase 55 costs are not deducted again.",
}


def _safe_input(value):
    """No arbitrary attachment metadata, paths or credential fields in this contract."""
    if isinstance(value, dict):
        for key, item in value.items():
            if re.search(r"password|secret|api.?key|credential|token|broker|environment|path", key, re.I):
                raise ValueError("paths, credentials and environment metadata are not accepted")
            _safe_input(item)
    elif isinstance(value, list):
        for item in value:
            _safe_input(item)
    elif isinstance(value, str) and re.search(r"[A-Za-z]:[\\/]|\\\\|file://|(?:^|\s)/(?!\s)", value, re.I):
        raise ValueError("machine-local paths are not accepted")


def fingerprints(request: RunCreate, pinned):
    definitions = []
    for d in request.definitions:
        data = d.model_dump(exclude={"dataset_version_id"})
        data["dataset_link"] = pinned["datasets"][d.strategy_id]
        definitions.append({**data, "definition_fingerprint": sha256_hex(data)})
    parts = {"universe": sha256_hex(definitions),
             "observations": sha256_hex([r.model_dump() for r in request.observations]),
             "ensemble_policy": sha256_hex({"policy": request.policy.model_dump(), "weights_available_at": request.weights_available_at}),
             "analysis_policy": sha256_hex({"policy": request.analysis.model_dump(),
                                            "scenarios": [s.model_dump() for s in request.scenarios], "links": pinned})}
    parts["configuration"] = sha256_hex({"schema_version": SCHEMA_VERSION, **parts})
    return parts


def create_run(payload, demo_key=None):
    request = RunCreate.model_validate(payload)
    _safe_input(request.model_dump())
    for policy in [request.policy, *[s.policy for s in request.scenarios]]:
        core.weight_details(policy, [d.strategy_id for d in request.definitions], request.analysis.tolerance)
    pinned = links.snapshot(request)
    return store.insert(request.model_dump(), pinned, fingerprints(request, pinned), demo_key)


def get_run(run_id):
    run = store.get(run_id)
    if run is None:
        raise NotFoundError("strategy ensemble run not found")
    return run


def _verify(run, *, require_result=False):
    request = RunCreate.model_validate(run["request"])
    expected = fingerprints(request, run["links"])
    if any(run["fingerprints"].get(k) != v for k, v in expected.items()):
        raise ConflictError("stored input fingerprints do not match")
    try:
        current_links = links.snapshot(request)
    except ValueError as exc:
        raise ConflictError("a linked source is unavailable or invalid; create a new run") from exc
    if current_links != run["links"]:
        raise ConflictError("a linked source changed; create a new run")
    if require_result and (not run["results"] or run["fingerprints"].get("result") != sha256_hex(
            {"configuration": expected["configuration"], "results": run["results"]})):
        raise ConflictError("stored result fingerprint does not match")
    return request


def execute_run(run_id, create_experiment=False):
    run = get_run(run_id)
    if run["status"] == "invalidated":
        raise ConflictError("invalidated runs cannot execute")
    request = _verify(run)
    try:
        definitions = {d.strategy_id: d for d in request.definitions}
        for r in request.observations:
            if (r.information_available_at < r.period_end or
                    definitions[r.strategy_id].configuration_available_at > r.period_start or
                    request.weights_available_at > r.period_start):
                raise ValueError("timing violation: outcomes must be known at/after period end; configurations and weights at/before period start")
        result = core.analyze(request)
        result["regimes"], result["validation"] = links.evaluate(request, run["links"], result)
        result.update(integrity="declared_timing_passed", warnings=WARNINGS, deferred=DEFERRED)
        result["baseline_eligible"] = (
            result["ensemble"]["n"] >= request.analysis.minimum_samples and
            all(s["coverage_ratio"] == 1 for s in result["coverage"]["strategies"]) and
            result["ensemble"]["reconciliation_max_residual"] <= request.analysis.tolerance and
            result["ensemble"]["costs"]["basis"] in ("gross", "net_of_strategy_costs") and
            all(d.leverage_convention != "unknown" for d in request.definitions) and
            (not run["links"]["regime"] or run["links"]["regime"]["integrity_status"] in (
                "declared", "verified_causal_rule", "verified_from_validation_split")))
        result["definition_fingerprints"] = {
            d.strategy_id: sha256_hex({**d.model_dump(exclude={"dataset_version_id"}),
                                      "dataset_link": run["links"]["datasets"][d.strategy_id]})
            for d in request.definitions}
        fps = {**run["fingerprints"], "result": sha256_hex({"configuration": run["fingerprints"]["configuration"], "results": result})}
    except ValueError as exc:
        with store.connection() as conn:
            conn.execute("""UPDATE strategy_ensemble_runs SET status='failed',results_json=NULL,
                is_baseline=0,error_message=?,updated_at=?,fingerprints_json=? WHERE id=? AND status!='invalidated'""",
                         (str(exc), store.now(), canonical_json({k: v for k, v in run["fingerprints"].items() if k != "result"}), run_id))
        raise
    record = False
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        current = store.get(run_id, conn)
        if current["status"] == "invalidated":
            raise ConflictError("run was invalidated while executing")
        _verify(current)
        record = create_experiment and not current["experiment_requested"]
        conn.execute("""UPDATE strategy_ensemble_runs SET status='completed',results_json=?,
            fingerprints_json=?,error_message=NULL,updated_at=?,experiment_requested=? WHERE id=?""",
                     (canonical_json(result), canonical_json(fps), store.now(),
                      int(record or current["experiment_requested"]), run_id))
    if record:
        exp = record_experiment(name=run["name"], module="strategy_ensemble_diagnostics", experiment_type="diagnostic",
                                parameters={"fingerprints": fps, "strategy_count": len(request.definitions),
                                            "observation_count": len(request.observations), "mode": request.policy.mode,
                                            "alignment": request.policy.alignment},
                                metrics={"integrity": result["integrity"], "common_periods": result["ensemble"]["n"],
                                         "cost_completeness": result["ensemble"]["costs"]["completeness"]})
        with store.connection() as conn:
            conn.execute("UPDATE strategy_ensemble_runs SET experiment_id=? WHERE id=?", (exp["id"] if exp else None, run_id))
    return get_run(run_id)


def invalidate(run_id, reason):
    get_run(run_id)
    with store.connection() as conn:
        conn.execute("""UPDATE strategy_ensemble_runs SET status='invalidated',is_baseline=0,
            error_message=?,updated_at=? WHERE id=?""", (reason, store.now(), run_id))
    return get_run(run_id)


def mark_baseline(run_id):
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        run = store.get(run_id, conn)
        if run is None:
            raise NotFoundError("strategy ensemble run not found")
        if run["status"] != "completed":
            raise ConflictError("only completed runs may be baselines")
        _verify(run, require_result=True)
        if not run["results"]["baseline_eligible"]:
            raise ConflictError("baseline requires full coverage, declared timing, known basis/leverage and reconciliation")
        scope = sha256_hex({k: run["fingerprints"][k] for k in ("universe", "observations")})
        conn.execute("UPDATE strategy_ensemble_runs SET is_baseline=0 WHERE baseline_scope=?", (scope,))
        conn.execute("UPDATE strategy_ensemble_runs SET is_baseline=1,baseline_scope=?,updated_at=? WHERE id=?",
                     (scope, store.now(), run_id))
    return get_run(run_id)


def compare(a, b):
    if a == b:
        raise ValueError("choose two different runs")
    runs = [get_run(a), get_run(b)]
    for run in runs:
        if run["status"] != "completed":
            raise ConflictError("comparison requires completed runs")
        _verify(run, require_result=True)
    same = all(runs[0]["fingerprints"][k] == runs[1]["fingerprints"][k] for k in ("universe", "observations"))
    return {"comparable_inputs": same, "reason": "Same universe and observations" if same else "Different sources or observation samples; descriptive side-by-side only",
            "runs": [{"id": r["id"], "name": r["name"], "fingerprints": r["fingerprints"],
                      "ensemble": {k: r["results"]["ensemble"][k] for k in ("n", "weights", "mean_return", "volatility_per_period", "costs")}}
                     for r in runs]}


def export(run_id):
    run = get_run(run_id)
    _verify(run, require_result=run["status"] == "completed")
    return {"schema_version": SCHEMA_VERSION, "name": run["name"], "status": run["status"],
            "request": run["request"], "source_identities": run["links"], "results": run["results"],
            "fingerprints": run["fingerprints"], "warnings": WARNINGS,
            "provenance": "supplied strategy returns; declarations are not independently verified"}
