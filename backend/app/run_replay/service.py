"""Stored-material verification. GET paths never execute research or fetch data."""
import hashlib
from contextlib import closing
from datetime import date, timedelta
from uuid import uuid4

from app.db import get_connection
from app.reproducibility import canonical_json
from app.cost_model import resolve as resolve_cost
from . import adapter, environment, store
from .identity import MAX_CSV, digest, full_hash, legacy, loads, validate


class Missing(LookupError):
    pass


class Changed(ValueError):
    pass


def dataset_pin(version_id):
    from app.ml_lifecycle.service import dataset_binding
    version, material = dataset_binding(version_id)
    return {"version_id": version_id, "material_hash": material,
            "content_hash": version.get("content_fingerprint"), "manifest_hash": version.get("manifest_fingerprint")}


def artifact_pin(run_id):
    # Explicit provenance reference only, not predictions or strategy returns.
    from app.ml_lifecycle.service import get_run
    record = get_run(run_id)
    if record["integrity"] != "intact" or record["completeness"] != "complete":
        raise ValueError("Optional lifecycle provenance is incomplete or changed")
    return {"run_id": run_id, "role": "provenance_only", "material_hash": digest({key: record[key] for key in
            ("lifecycle_hash", "snapshot_hash", "dataset_material_hash", "identities", "links")})}


def positive_id(value):
    if type(value) is not int or not 0 < value <= 2**31 - 1:
        raise ValueError("References must be positive bounded integer IDs")
    return value


def result_identity(data):
    fields = {key: data[key] for key in ("ticker", "strategy", "start_date", "end_date", "initial_capital",
              "transaction_cost_bps", "params", "metrics", "equity_curve", "trades")}
    # SQLite REAL columns return floats even when a caller supplied an integer.
    for key in ("initial_capital", "transaction_cost_bps"):
        fields[key] = float(fields[key])
    return digest(fields)


def csv_input(text, config):
    from app.csv_data import parse_price_csv
    if type(text) is not str or len(text.encode("utf-8")) > MAX_CSV:
        raise ValueError("Retained/reselected CSV must be at most 128 KiB")
    raw = text.encode("utf-8")
    fingerprint = hashlib.sha256(raw).hexdigest()
    if fingerprint != config.get("dataset_fingerprint"):
        raise ValueError("CSV content differs from the historical input hash")
    close = parse_price_csv(raw)
    if len(close) > 2000:
        raise ValueError("Replay CSV exceeds the 2000-row v1 bound")
    if str(close.index[0].date()) != config["start_date"] or str(close.index[-1].date()) != config["end_date"]:
        raise ValueError("CSV dates differ from the canonical range")
    close.attrs["csv_content_sha256"] = fingerprint
    return close


def register_in_transaction(conn, saved_id, data, capture=None):
    existing = conn.execute("SELECT id FROM run_replay_contexts WHERE saved_backtest_id=?", (saved_id,)).fetchone()
    if existing:
        return existing[0]
    config = legacy(data.get("params", {}).get("reproducibility"))
    capture = capture or {}
    validate(capture, limit=256 * 1024)
    allowed = {"schema_version", "original_request", "request_provenance", "execution_environment", "dataset_version_id", "csv_text", "artifact_run_id", "parent_context_id"}
    if set(capture) - allowed or capture and capture.get("schema_version") != "replay_capture_v1":
        raise ValueError("Unsupported replay capture fields/schema")
    original = capture.get("original_request")
    provenance = capture.get("request_provenance", "declared_request" if original else "unknown")
    if provenance not in ("wire_json", "validated_model_with_defaults", "declared_request", "unknown"):
        raise ValueError("Unknown request collection provenance")
    if original is not None:
        adapter.restore(config, original)
    for key in ("ticker", "strategy", "start_date", "end_date", "initial_capital"):
        value = data[key].strip().upper() if key == "ticker" else data[key]
        if value != config.get(key):
            raise ValueError("Saved result identity disagrees with canonical configuration")
    if round(data["transaction_cost_bps"], 6) != config["cost_model"]["effective_cost_bps"]:
        raise ValueError("Saved effective costs disagree with canonical configuration")
    execution_env = capture.get("execution_environment")
    if execution_env is not None:
        environment.check(execution_env)
    pin = dataset_pin(positive_id(capture["dataset_version_id"])) if capture.get("dataset_version_id") is not None else None
    csv = capture.get("csv_text")
    if csv is not None:
        if config.get("data_provider") != "csv_upload" or pin is None:
            raise ValueError("Retained CSV requires an explicit Dataset Registry version")
        close = csv_input(csv, config)
        if pin["content_hash"] != config.get("dataset_fingerprint"):
            raise ValueError("Dataset content declaration differs from retained CSV")
        from app.dataset_registry.store import get_version
        version = get_version(pin["version_id"])
        expected = [{"name": "date", "type": "date", "nullable": False}, {"name": "close", "type": "float64", "nullable": False}]
        if version["row_count"] != len(close) or version["column_count"] != 2 or version["schema_snapshot"]["fields"] != expected:
            raise ValueError("Dataset row count or parsed price-series schema does not match")
    artifact = artifact_pin(positive_id(capture["artifact_run_id"])) if capture.get("artifact_run_id") is not None else None
    parent = capture.get("parent_context_id")
    if parent is not None:
        positive_id(parent)
        if store.get(parent) is None:
            raise ValueError("Parent replay context does not exist")
    inputs = {"schema_version": "replay_input_v1", "adapter": "sma_v1" if config.get("strategy") == "sma_crossover" else "config_only",
              "canonical_config": config, "dataset": pin, "artifact": artifact,
              "effective_cost_bps": resolve_cost(adapter.request_model(original).cost_model, original.get("transaction_cost_bps", 10)).effective_bps_per_side if original else None,
              "diagnostics": {key: original.get(key) for key in ("robustness", "sensitivity")} if original else None}
    snapshot = {"schema_version": "replay_context_v1", "config": config, "original_request": original,
                "request_provenance": provenance,
                "inputs": inputs, "input_hash": digest(inputs), "execution_environment": execution_env,
                "environment_hash": digest(execution_env) if execution_env else None,
                "environment_trust": "declared_execution_metadata_not_attestation" if execution_env else "unknown",
                "save_environment": environment.collect("save"), "result_hash": result_identity(data),
                "csv_text": csv, "parent_context_id": parent, "saved_backtest_id": saved_id}
    created_at = conn.execute("SELECT created_at FROM saved_backtests WHERE id=?", (saved_id,)).fetchone()[0]
    snapshot["execution_hash"] = digest({"schema_version": "saved_execution_v1", "saved_backtest_id": saved_id,
        "created_at": created_at, "result_hash": snapshot["result_hash"], "input_hash": snapshot["input_hash"],
        "environment_hash": snapshot["environment_hash"]})
    encoded = validate(snapshot, limit=512 * 1024)
    full = data["params"]["reproducibility"]["config_hash_full"]
    cursor = conn.execute("INSERT INTO run_replay_contexts(saved_backtest_id, config_hash_full, config_schema, snapshot_json, snapshot_hash) VALUES(?,?,?,?,?)",
                          (saved_id, full, config["schema_version"], encoded, digest(snapshot)))
    conn.execute("UPDATE saved_backtests SET config_hash_full=?, config_schema=? WHERE id=?", (full, config["schema_version"], saved_id))
    return cursor.lastrowid


def verified(row):
    from app.saved_backtests import get_saved_backtest
    try:
        snap = loads(row["snapshot_json"], limit=512 * 1024)
        if digest(snap) != row["snapshot_hash"] or snap["saved_backtest_id"] != row["saved_backtest_id"]:
            raise ValueError("Snapshot integrity mismatch")
        saved = get_saved_backtest(row["saved_backtest_id"])
        if saved is None:
            raise ValueError("Historical saved result is missing")
        config = legacy(saved["params"].get("reproducibility"))
        if canonical_json(config) != canonical_json(snap["config"]) or saved["config_hash_full"] != row["config_hash_full"]:
            raise ValueError("Canonical/index identity mismatch")
        if saved["config_schema"] != row["config_schema"] or saved["params"]["reproducibility"]["config_hash_full"] != row["config_hash_full"]:
            raise ValueError("Schema/hash index mismatch")
        if snap["input_hash"] != digest(snap["inputs"]) or result_identity(saved) != snap["result_hash"]:
            raise ValueError("Input or historical result content changed")
        if snap["environment_hash"] != (digest(snap["execution_environment"]) if snap["execution_environment"] else None):
            raise ValueError("Execution environment changed")
        execution = {"schema_version": "saved_execution_v1", "saved_backtest_id": saved["id"], "created_at": saved["created_at"],
                     "result_hash": snap["result_hash"], "input_hash": snap["input_hash"], "environment_hash": snap["environment_hash"]}
        if snap["execution_hash"] != digest(execution):
            raise ValueError("Saved execution identity changed")
        return snap, saved
    except (ValueError, KeyError, TypeError) as exc:
        raise Changed("Stored replay content is corrupt or changed: " + str(exc)) from exc


def resolve_hash(value, page=1, page_size=20):
    full_hash(value)
    rows, total = store.contexts(value, (page - 1) * page_size, page_size)
    if total == 0:
        raise Missing("Full configuration hash is not registered")
    contexts = []
    config = None
    for row in rows:
        snap, saved = verified(row)
        config = snap["config"]
        contexts.append({"id": row["id"], "saved_backtest_id": saved["id"], "name": saved["name"],
                         "created_at": saved["created_at"], "input_hash": snap["input_hash"],
                         "environment_hash": snap["environment_hash"], "result_hash": snap["result_hash"]})
        contexts[-1]["execution_hash"] = snap["execution_hash"]
    if config is None:
        raise Missing("No contexts on this page")
    return {"config_hash_full": value, "config_hash": value[:12], "canonical_config": config,
            "contexts": contexts, "total": total, "page": page, "page_size": page_size,
            "selection_required": True, "ambiguous": total > 1}


def preflight(context_id):
    row = store.get(context_id)
    if row is None:
        raise Missing("Replay context not found")
    snap, saved = verified(row)
    messages = []
    integrity = "intact"
    for key, checker, id_key in (("dataset", dataset_pin, "version_id"), ("artifact", artifact_pin, "run_id")):
        pin = snap["inputs"][key]
        if pin:
            try:
                if checker(pin[id_key]) != pin:
                    raise ValueError("material changed")
            except (ValueError, LookupError, KeyError, TypeError):
                integrity = "changed"
                messages.append(key + " is missing, changed, invalidated or incomplete")
    try:
        request = adapter.restore(snap["config"], snap["original_request"])
    except (ValueError, KeyError, TypeError):
        request = None
        messages.append("No lossless v1 SMA restore adapter for this configuration")
    provider = snap["config"].get("data_provider")
    availability = "provider_not_retained" if provider == "yfinance" else "reselection_required"
    if snap["csv_text"] is not None:
        csv_input(snap["csv_text"], snap["config"])
        availability = "retained_verified" if integrity == "intact" else "changed"
    if snap["original_request"] is None:
        messages.append("Original request and optional diagnostic settings are unknown; only known canonical settings can be restored")
    if availability == "provider_not_retained":
        messages.append("Historical provider prices were not retained. Run will explicitly request current provider history")
    if availability == "reselection_required":
        messages.append("Reselect the original CSV; its hash alone cannot recover missing input")
    current = environment.collect("inspection")
    return {"schema_version": "replay_preflight_v1", "context_id": context_id,
            "config_hash_full": row["config_hash_full"], "canonical_config": snap["config"],
            "input_hash": snap["input_hash"], "environment_hash": snap["environment_hash"], "result_hash": snap["result_hash"],
            "execution_hash": snap["execution_hash"],
            "original_request": snap["original_request"], "restore_request": request,
            "request_provenance": snap["request_provenance"],
            "restore_level": "recorded_settings" if snap["original_request"] else "config_only",
            "dataset": snap["inputs"]["dataset"], "artifact": snap["inputs"]["artifact"],
            "data_availability": availability, "integrity": integrity,
            "ready_with_retained_data": bool(request and availability == "retained_verified" and integrity == "intact"),
            "execution_environment": snap["execution_environment"], "save_environment": snap["save_environment"],
            "inspection_environment": current, "environment_comparison": environment.compare(snap["execution_environment"], current),
            "limitations": messages + ["Matching manifests do not guarantee bit-identical results. Execution metadata is declared, not attested."]}


def export_context(context_id):
    result = preflight(context_id)
    if result["restore_request"] is None:
        raise ValueError("Unsupported schema/adapter has no safe v1 export contract")
    result["schema_version"] = "replay_export_v1"
    result["data_included"] = False
    return result


def register_legacy(saved_id):
    from app.saved_backtests import get_saved_backtest
    data = get_saved_backtest(saved_id)
    if data is None:
        raise Missing("Saved backtest not found")
    with closing(get_connection()) as conn, conn:
        context_id = register_in_transaction(conn, saved_id, data)
    return preflight(context_id)


def check_input(context_id, text):
    result = preflight(context_id)
    if result["integrity"] != "intact" or result["canonical_config"].get("data_provider") != "csv_upload":
        raise Changed("Local replay input context is not intact")
    csv_input(text, result["canonical_config"])
    return {"matched": True, "context_id": context_id}


def execute_local(context_id, raw_request, text=None):
    result = preflight(context_id)
    if result["integrity"] != "intact" or result["restore_request"] is None:
        raise Changed("Cannot execute a changed/unsupported local replay context")
    if result["canonical_config"].get("data_provider") != "csv_upload":
        raise ValueError("This explicit action only executes local CSV contexts")
    row = store.get(context_id)
    snap, _ = verified(row)
    close = csv_input(text if text is not None else snap["csv_text"], snap["config"])
    request = adapter.request_model(raw_request)
    if request.benchmark and request.benchmark.mode == "custom_ticker":
        raise ValueError("Local replay cannot fetch a custom remote benchmark")
    for key in ("ticker", "start_date", "end_date"):
        value = getattr(request, key).strip().upper() if key == "ticker" else getattr(request, key)
        if value != snap["config"][key]:
            raise ValueError("Local replay v1 keeps the retained ticker/date range fixed; use CSV Upload for a different range")
    from app.main import _run_csv_single_asset
    response = _run_csv_single_asset(close, "sma_crossover", request.model_dump(mode="json"), request.ticker)
    capture = response.execution_context
    capture["parent_context_id"] = context_id
    if snap["inputs"]["dataset"]:
        capture["dataset_version_id"] = snap["inputs"]["dataset"]["version_id"]
        capture["csv_text"] = text if text is not None else snap["csv_text"]
    return response


def demo():
    from app.dataset_registry import service as datasets
    from app.dataset_registry.models import DatasetCreate, VersionCreate
    from app.main import _run_csv_single_asset
    from app.saved_backtests import create_saved_backtest
    import math
    token = uuid4().hex
    lines = ["date,close"] + [f"{date(2020, 1, 1) + timedelta(days=i)},{100 + i * .08 + 8 * math.sin(i / 7):.6f}" for i in range(180)]
    text = "\n".join(lines) + "\n"
    raw_hash = hashlib.sha256(text.encode()).hexdigest()
    dataset = datasets.create_dataset(DatasetCreate(name="Run Replay demo " + token[:8], domain="backtest",
        dataset_type="price_series", source_type="generated", is_demo=True).model_dump(mode="json"))
    fields = [{"name": "date", "type": "date", "nullable": False}, {"name": "close", "type": "float64", "nullable": False}]
    version = datasets.create_version(dataset["id"], VersionCreate(version_label="v1", row_count=180, column_count=2,
        content_fingerprint=raw_hash, file_size_bytes=len(text.encode()), deterministic=True,
        storage_locator="generated://run-replay/" + token, schema_snapshot={"fields": fields, "ordering_significant": True}).model_dump(mode="json"))
    from app.csv_data import parse_price_csv
    close = parse_price_csv(text.encode())
    close.attrs["csv_content_sha256"] = raw_hash
    result = _run_csv_single_asset(close, "sma_crossover", {"fast_window": 5, "slow_window": 20, "initial_capital": 100000, "transaction_cost_bps": 10}, "REPLAY-DEMO")
    result.execution_context.update(dataset_version_id=version["id"], csv_text=text)
    payload = {"name": "Local SMA replay demo", "ticker": result.ticker, "strategy": result.strategy,
        "start_date": result.start_date, "end_date": result.end_date, "initial_capital": result.initial_capital,
        "transaction_cost_bps": result.transaction_cost_bps, "params": {"reproducibility": result.reproducibility.model_dump(mode="json")},
        "metrics": result.strategy_metrics.model_dump(mode="json"), "equity_curve": [p.model_dump(mode="json") for p in result.equity_curve],
        "trades": [p.model_dump(mode="json") for p in result.trades], "notes": "Deterministic local data, not market performance.", "replay": result.execution_context}
    saved = create_saved_backtest(payload)
    rows, _ = store.contexts(saved["config_hash_full"], limit=50)
    row = next(row for row in rows if row["saved_backtest_id"] == saved["id"])
    return {"saved_backtest_id": saved["id"], "config_hash_full": saved["config_hash_full"], "context_id": row["id"]}
