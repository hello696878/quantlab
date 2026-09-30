"""Explicit registration/link actions and read-only integrity verification."""

from app.dataset_registry import service as datasets, store as dataset_store
from app.dataset_registry.models import DatasetCreate, VersionCreate

from . import adapters, store
from .identity import fingerprint
from .models import Registration
from .validation import identities, validate


class NotFoundError(LookupError):
    pass


class ConflictError(ValueError):
    pass


def dataset_binding(version_id):
    """Hash actual stored scientific metadata; never read a dataset locator."""
    version = dataset_store.get_version(version_id)
    if version is None:
        raise ConflictError("an existing Dataset Registry version is required")
    if version.get("invalidated_at"):
        raise ConflictError("dataset version is invalidated")
    dataset = dataset_store.get_dataset(version["dataset_id"])
    if dataset is None or not dataset.get("is_active"):
        raise ConflictError("dataset is missing or inactive")
    dataset_fields = {k: v for k, v in dataset.items() if k not in
                      {"id", "created_at", "updated_at", "current_version_id", "provenance_status"}}
    version_fields = {k: v for k, v in version.items() if k not in
                      {"id", "dataset_id", "created_at", "storage_locator", "storage_locator_type"}}
    return version, fingerprint("dataset_binding", {"dataset": dataset_fields, "version": version_fields})


def register(payload, *, demo_key=None):
    request = Registration.model_validate(payload).model_dump(mode="json")
    snapshot = request["snapshot"]
    validate(snapshot, allow_demo=demo_key is not None)
    try:
        version, material_hash = dataset_binding(request["dataset_version_id"])
    except LookupError as exc:
        raise ValueError("an existing Dataset Registry version is required") from exc
    if version.get("invalidated_at"):
        raise ConflictError("dataset version is invalidated")
    if version.get("content_fingerprint") != request["dataset_content_hash"] or snapshot["source_hash"] != request["dataset_content_hash"]:
        raise ValueError("dataset content fingerprint must match the actual source snapshot")
    if snapshot["origin"] == "deterministic_demo":
        source = snapshot["source"]
        schema = version.get("schema_snapshot", {})
        if (version.get("row_count") != len(source["rows"]) or version.get("column_count") != len(source["columns"])
                or schema.get("fields") != source["columns"] or not schema.get("ordering_significant")):
            raise ValueError("dataset schema, column order and row count must match the retained source")
    identity = identities(snapshot)["lifecycle"]
    record = store.insert(request, identity, fingerprint("snapshot", snapshot), version["manifest_fingerprint"], demo_key,
                          dataset_material_hash=material_hash)
    return get_run(record["id"])


def get_run(run_id):
    record = store.get(run_id)
    if record is None:
        raise NotFoundError("ML lifecycle not found")
    errors = []
    artifact_ids = {"lifecycle": record["lifecycle_hash"]}
    try:
        validate(record["snapshot"], allow_demo=record["trusted_demo"])
        artifact_ids = identities(record["snapshot"])
        if fingerprint("snapshot", record["snapshot"]) != record["snapshot_hash"] or identities(record["snapshot"])["lifecycle"] != record["lifecycle_hash"]:
            raise ValueError("stored snapshot content mismatch")
        version, material_hash = dataset_binding(record["dataset_version_id"])
        if (material_hash != record.get("dataset_material_hash") or
                version.get("content_fingerprint") != record["dataset_content_hash"] or
                version["manifest_fingerprint"] != record["dataset_manifest_hash"]):
            raise ValueError("dataset binding changed or was invalidated")
    except (ValueError, LookupError, KeyError, TypeError):
        errors.append("Snapshot or dataset binding is missing, invalidated or has changed.")
    links = store.links(run_id)
    for link in links:
        link["integrity"] = "unavailable"
        if link["status"] == "completed":
            try:
                if adapters.content(link["adapter"], link["destination_id"]) != link["content_hash"]:
                    raise ValueError("linked content mismatch")
                link["integrity"] = "intact"
            except (ValueError, LookupError, KeyError, TypeError):
                link["integrity"] = "changed"
                errors.append("Linked " + link["adapter"] + " content changed or was invalidated.")
        link["workspace"] = adapters.ADAPTERS[link["adapter"]][3]
    complete = record["trusted_demo"] and len(links) == len(adapters.ADAPTERS) and all(l["status"] == "completed" and l["integrity"] == "intact" for l in links)
    record.update(stored_status="stored", processing_status="failed" if any(l["status"] == "failed" for l in links) else
                  "running" if any(l["status"] == "running" for l in links) else "idle",
                  completeness="complete" if complete and not errors else "incomplete",
                  integrity="changed" if errors else "intact", integrity_messages=errors, links=links,
                  validation_state="internally_generated_held_out" if record["trusted_demo"] and not errors else "unverified",
                  identities=artifact_ids)
    return record


def list_runs(page=1, page_size=20, completeness=None, integrity=None):
    # Bounded v1 registry. Dynamic linked integrity is checked before filtering,
    # so an invalidated record cannot disappear behind a cached green badge.
    ids = store.ids()
    if len(ids) > 500:
        raise ConflictError("registry exceeds the v1 500-record inspection bound")
    items = []
    for run_id in ids:
        row = get_run(run_id)
        if completeness and row["completeness"] != completeness or integrity and row["integrity"] != integrity:
            continue
        items.append({k: row[k] for k in ("id", "name", "created_at", "lifecycle_hash", "dataset_version_id", "stored_status",
                                         "processing_status", "completeness", "integrity", "validation_state")})
    return {"items": items[(page - 1) * page_size:page * page_size], "total": len(items), "page": page, "page_size": page_size}


def link(run_id, adapter):
    if adapter not in adapters.ADAPTERS:
        raise ValueError("unknown lifecycle adapter")
    record = get_run(run_id)
    if record["integrity"] != "intact":
        raise ConflictError("cannot execute with changed provenance")
    if not record["trusted_demo"]:
        raise ValueError("legacy source lacks required feature/membership provenance for adapters")
    links = {l["adapter"]: l for l in record["links"]}
    if not store.claim(run_id, adapter):
        if links.get(adapter, {}).get("status") == "running":
            raise ConflictError("adapter is already running; interrupted jobs require operator inspection")
        return record
    try:
        destination = adapters.create(adapter, record, links, f"ml-lifecycle:{run_id}:{adapter}")
        store.update_link(run_id, adapter, "running", destination_id=destination)
        digest = adapters.execute(adapter, destination, record)
        store.update_link(run_id, adapter, "completed", destination_id=destination, content_hash=digest)
    except Exception:
        # No paths/provider payloads or exception representations in exported state.
        store.update_link(run_id, adapter, "failed", error="Adapter failed; retry the explicit action after resolving the input or service error.")
        raise
    return get_run(run_id)


def export(run_id):
    record = get_run(run_id)
    if record["integrity"] != "intact":
        raise ConflictError("cannot export changed or invalidated provenance")
    return {"schema_version": 1, "type": "quantlab_ml_lifecycle", "lifecycle": record,
            "caveat": "Integrity hashes are not proof of authenticity, profitability or suitability. No executable model or replay."}


def compare(a, b):
    records = [export(i)["lifecycle"] for i in (a, b)]
    return {"schema_version": 1, "a": a, "b": b, "note": "Neutral comparison; no ranking or promotion.",
            "rows": [{"field": key, "a": records[0][key], "b": records[1][key]} for key in
                     ("name", "dataset_content_hash", "completeness", "validation_state", "identities")],
            "metrics": [r["snapshot"].get("evaluation", {}).get("metrics") for r in records]}


def demo():
    from .demo import DEMO_KEY, fit_snapshot, prepare_demo

    run_id = store.demo_id(DEMO_KEY)
    if run_id is None:
        snapshot = fit_snapshot(prepare_demo())
        validate(snapshot, allow_demo=True)
        dataset_id = dataset_store.dataset_demo_key_id(DEMO_KEY)
        if dataset_id is None:
            request = DatasetCreate(name="Phase 65 synthetic ES lifecycle", domain="futures", dataset_type="continuous_prices",
                                    source_type="deterministic_fixture", is_demo=True,
                                    description="Fixed-seed synthetic ES prices, not market data.").model_dump(mode="json")
            dataset_id = datasets.create_dataset(request, demo_key=DEMO_KEY)["id"]
        version_id = dataset_store.version_demo_key_id(DEMO_KEY)
        if version_id is None:
            source = snapshot["source"]
            request = VersionCreate(version_label="v1", format="json", storage_locator="fixture://phase65/lifecycle-v1",
                                    row_count=len(source["rows"]), column_count=len(source["columns"]),
                                    content_fingerprint=snapshot["source_hash"], deterministic=True,
                                    schema_snapshot={"fields": source["columns"], "ordering_significant": True},
                                    provenance={"source": "repository-owned synthetic fixture", "seed": 650}).model_dump(mode="json")
            version_id = datasets.create_version(dataset_id, request, demo_key=DEMO_KEY)["id"]
        record = register({"name": "Synthetic ES held-out logistic lifecycle", "dataset_version_id": version_id,
                           "dataset_content_hash": snapshot["source_hash"], "snapshot": snapshot}, demo_key=DEMO_KEY)
        run_id = record["id"]
    for adapter in adapters.ADAPTERS:
        try:
            link(run_id, adapter)
        except (ValueError, RuntimeError, LookupError):
            # The explicit action returns the honest partial record. Retrying
            # reuses each destination's unique ownership key, never other demos.
            break
    return get_run(run_id)
