"""
Service + persistence tests for the Dataset Lineage registry (Phase 49.0).

Fresh temporary SQLite database per test.  Covers schema creation (fresh +
pre-existing DB upgrade), dataset CRUD, version immutability + invalidation,
lineage rules (chain / branch / merge / duplicate / self / direct + indirect
cycle / invalidated ancestor / depth bound), provenance derivation, quality
persistence + rollup, comparison, experiment links, and demo idempotence.
"""

from __future__ import annotations

import sqlite3

import pytest

db_module = pytest.importorskip("app.db")
store = pytest.importorskip("app.dataset_registry.store")
service = pytest.importorskip("app.dataset_registry.service")
lineage = pytest.importorskip("app.dataset_registry.lineage")
demo = pytest.importorskip("app.dataset_registry.demo")
exp_service = pytest.importorskip("app.experiment_registry.service")


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


def _dataset(**over):
    payload = {
        "name": over.pop("name", "DS"),
        "domain": "equities",
        "dataset_type": "prices",
        "source_type": "deterministic_fixture",
        "format": "csv",
    }
    payload.update(over)
    return service.create_dataset(payload)


def _version(dataset_id, label="v1", **over):
    payload = {
        "version_label": label,
        "storage_locator": over.pop("storage_locator", f"fixture://test/{label}"),
        "format": "csv",
        "deterministic": True,
        "row_count": 100,
        "schema_snapshot": {
            "fields": [
                {"name": "date", "type": "date", "nullable": False},
                {"name": "close", "type": "float", "nullable": True},
            ],
            "ordering_significant": False,
        },
        "provenance": {"source": "test fixture"},
        "content_fingerprint": "c" * 64,
    }
    payload.update(over)
    return service.create_version(dataset_id, payload)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_fresh_db_creates_all_tables(tmp_path, monkeypatch):
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    conn = sqlite3.connect(str(db_file))
    try:
        names = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    for table in (
        "datasets",
        "dataset_versions",
        "dataset_lineage",
        "dataset_quality_results",
        "experiment_dataset_links",
    ):
        assert table in names


def test_existing_db_upgrade_preserves_experiment_registry(tmp_path, monkeypatch):
    # A DB created before this phase (has experiment_registry data) upgrades
    # in place and keeps its rows.
    db_file = tmp_path / "legacy.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    exp = exp_service.create_experiment(
        {"name": "Kept", "module": "m", "experiment_type": "t"}, source="test"
    )
    db_module.init_db()  # idempotent re-run
    assert exp_service.get_experiment(exp["id"])["name"] == "Kept"


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


def test_dataset_create_get_update():
    d = _dataset(name="Prices")
    assert d["id"] >= 1
    got = service.get_dataset(d["id"])
    assert got["name"] == "Prices"
    assert got["version_count"] == 0
    updated = service.update_dataset(d["id"], {"notes": "hello", "tags": ["a"]})
    assert updated["notes"] == "hello"
    assert updated["tags"] == ["a"]


def test_dataset_name_conflict():
    _dataset(name="Same")
    with pytest.raises(service.ConflictError):
        _dataset(name="Same")


def test_dataset_not_found():
    with pytest.raises(service.NotFoundError):
        service.get_dataset(999)


def test_dataset_filters_and_pagination():
    _dataset(name="A", domain="macro")
    _dataset(name="B", domain="equities")
    res = service.list_datasets(filters={"domain": "macro"})
    assert res["total"] == 1
    for i in range(4):
        _dataset(name=f"P{i}")
    paged = service.list_datasets(filters={}, page=1, page_size=3)
    assert paged["total"] == 6
    assert len(paged["items"]) == 3
    assert paged["total_pages"] == 2


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


def test_version_create_sets_fingerprints_and_current():
    d = _dataset()
    v = _version(d["id"])
    assert v["manifest_fingerprint"]
    assert v["schema_fingerprint"]
    ds = service.get_dataset(d["id"])
    assert ds["current_version_id"] == v["id"]
    assert ds["provenance_status"] == "complete"  # identity + source + schema


def test_version_provenance_partial_and_unknown():
    d = _dataset(name="Partial")
    _version(d["id"], content_fingerprint=None, provenance={}, schema_snapshot={"fields": [
        {"name": "x", "type": "float", "nullable": True}], "ordering_significant": False})
    assert service.get_dataset(d["id"])["provenance_status"] == "partial"
    d2 = _dataset(name="Unknown")
    _version(d2["id"], content_fingerprint=None, provenance={},
             schema_snapshot={"fields": [], "ordering_significant": False})
    assert service.get_dataset(d2["id"])["provenance_status"] == "unknown"


def test_version_label_unique_per_dataset():
    d = _dataset()
    _version(d["id"], "v1")
    with pytest.raises(service.ConflictError):
        _version(d["id"], "v1")


def test_version_locator_validated():
    d = _dataset()
    with pytest.raises(service.DatasetError):
        _version(d["id"], storage_locator="C:\\abs\\path.csv")


def test_version_immutability_only_narrow_columns():
    d = _dataset()
    v = _version(d["id"])
    # Direct store-level attempt to change a core field is a no-op (whitelist).
    result = store.update_version_columns(v["id"], {"manifest_fingerprint": "x" * 64})
    assert result["manifest_fingerprint"] == v["manifest_fingerprint"]


def test_invalidation_preserves_record_lineage_and_links():
    d = _dataset()
    v1 = _version(d["id"], "v1")
    v2 = _version(d["id"], "v2")
    service.add_lineage(
        {
            "parent_version_id": v1["id"],
            "child_version_id": v2["id"],
            "relationship_type": "derived_from",
            "transformation_name": "t",
            "parameters": {},
        }
    )
    exp = exp_service.create_experiment(
        {"name": "E", "module": "m", "experiment_type": "t"}, source="test"
    )
    service.create_link(
        {"experiment_id": exp["id"], "dataset_version_id": v1["id"], "role": "input"}
    )
    inv = service.invalidate_version(v1["id"], "superseded")
    assert inv["invalidated_at"]
    assert inv["invalidation_reason"] == "superseded"
    # Record, lineage, and links all still there.
    assert store.get_version(v1["id"]) is not None
    assert len(store.edges_by_parent(v1["id"])) == 1
    assert len(store.links_for_version(v1["id"])) == 1
    with pytest.raises(service.ConflictError):
        service.invalidate_version(v1["id"], "again")


# ---------------------------------------------------------------------------
# Lineage rules
# ---------------------------------------------------------------------------


def _edge(parent, child, name="t", rel="derived_from"):
    return service.add_lineage(
        {
            "parent_version_id": parent,
            "child_version_id": child,
            "relationship_type": rel,
            "transformation_name": name,
            "parameters": {},
        }
    )


def test_lineage_chain_branch_merge():
    d = _dataset()
    a = _version(d["id"], "a")["id"]
    b = _version(d["id"], "b")["id"]
    c = _version(d["id"], "c")["id"]
    m = _version(d["id"], "m")["id"]
    _edge(a, b)          # chain
    _edge(a, c)          # branch
    _edge(b, m)          # merge (two parents)
    _edge(c, m, name="t2")
    graph = service.lineage_graph(m)
    ids = {n["version_id"] for n in graph["nodes"]}
    assert ids == {a, b, c, m}
    assert len(graph["edges"]) == 4


def test_lineage_duplicate_idempotent():
    d = _dataset()
    a = _version(d["id"], "a")["id"]
    b = _version(d["id"], "b")["id"]
    e1 = _edge(a, b)
    e2 = _edge(a, b)
    assert e1["id"] == e2["id"]


def test_lineage_self_and_cycles_rejected():
    d = _dataset()
    a = _version(d["id"], "a")["id"]
    b = _version(d["id"], "b")["id"]
    c = _version(d["id"], "c")["id"]
    with pytest.raises(service.DatasetError):
        _edge(a, a)
    _edge(a, b)
    with pytest.raises(service.DatasetError):
        _edge(b, a)          # direct cycle
    _edge(b, c)
    with pytest.raises(service.DatasetError):
        _edge(c, a)          # indirect cycle a→b→c→a


def test_lineage_missing_version_rejected():
    d = _dataset()
    a = _version(d["id"], "a")["id"]
    with pytest.raises(service.NotFoundError):
        _edge(a, 9999)


def test_lineage_invalidated_ancestor_stays_visible():
    d = _dataset()
    a = _version(d["id"], "a")["id"]
    b = _version(d["id"], "b")["id"]
    _edge(a, b)
    service.invalidate_version(a, "old")
    graph = service.lineage_graph(b)
    node_a = next(n for n in graph["nodes"] if n["version_id"] == a)
    assert node_a["invalidated"] is True


def test_lineage_depth_bound_truncates():
    d = _dataset()
    ids = [_version(d["id"], f"v{i}")["id"] for i in range(6)]
    for parent, child in zip(ids, ids[1:]):
        _edge(parent, child)
    graph = service.lineage_graph(ids[-1], max_depth=2, node_limit=50)
    depths = {n["version_id"]: n["depth"] for n in graph["nodes"]}
    assert max(depths.values()) <= 2
    assert graph["truncated"] is True


def test_lineage_node_limit_truncates():
    d = _dataset()
    root = _version(d["id"], "root")["id"]
    for i in range(5):
        child = _version(d["id"], f"c{i}")["id"]
        _edge(root, child, name=f"t{i}")
    graph = service.lineage_graph(root, max_depth=3, node_limit=3)
    assert len(graph["nodes"]) <= 3
    assert graph["truncated"] is True


# ---------------------------------------------------------------------------
# Quality persistence + comparison
# ---------------------------------------------------------------------------


def test_quality_run_persists_and_rolls_up():
    d = _dataset()
    v = _version(d["id"], statistics_summary={"missing_ratio": 0.5})
    results = service.run_quality_checks(
        v["id"], {"checks": ["row_count_nonzero", "missing_ratio_within_limit"], "expectations": {}}
    )
    assert len(results) == 2
    updated = service.get_version(v["id"])
    assert updated["quality_status"] == "warning"
    assert updated["validation_status"] == "checked"
    assert len(service.list_quality(v["id"])) == 2


def test_compare_versions_drift_and_fingerprints():
    d = _dataset()
    a = _version(d["id"], "a")
    b = _version(
        d["id"],
        "b",
        schema_snapshot={
            "fields": [
                {"name": "date", "type": "date", "nullable": False},
                {"name": "close", "type": "float", "nullable": True},
                {"name": "volume", "type": "integer", "nullable": True},
            ],
            "ordering_significant": False,
        },
        row_count=150,
    )
    cmp = service.compare_versions(a["id"], b["id"])
    assert cmp["drift_class"] == "compatible"
    assert cmp["fingerprints"]["manifest"] is False
    assert cmp["fingerprints"]["content"] is True  # same supplied content fp
    row_metric = next(m for m in cmp["metrics"] if m["field"] == "row_count")
    assert "Δ 50" in row_metric["note"]
    with pytest.raises(service.DatasetError):
        service.compare_versions(a["id"], a["id"])


# ---------------------------------------------------------------------------
# Experiment links
# ---------------------------------------------------------------------------


def test_link_create_hydrates_and_is_idempotent():
    d = _dataset()
    v = _version(d["id"])
    exp = exp_service.create_experiment(
        {"name": "E", "module": "m", "experiment_type": "t"}, source="test"
    )
    l1 = service.create_link(
        {"experiment_id": exp["id"], "dataset_version_id": v["id"], "role": "input"}
    )
    l2 = service.create_link(
        {"experiment_id": exp["id"], "dataset_version_id": v["id"], "role": "input"}
    )
    assert l1["id"] == l2["id"]
    assert l1["experiment_name"] == "E"
    assert l1["version_label"] == "v1"
    assert service.links_for_experiment(exp["id"])[0]["dataset_name"] == d["name"]


def test_link_fingerprint_match_flag():
    d = _dataset()
    v = _version(d["id"])  # content fp = "c"*64
    matching = exp_service.create_experiment(
        {"name": "M", "module": "m", "experiment_type": "t",
         "dataset_name": "x", "dataset_fingerprint": "c" * 64},
        source="test",
    )
    mismatching = exp_service.create_experiment(
        {"name": "X", "module": "m", "experiment_type": "t",
         "dataset_name": "x", "dataset_fingerprint": "d" * 64},
        source="test",
    )
    ok = service.create_link(
        {"experiment_id": matching["id"], "dataset_version_id": v["id"], "role": "input"}
    )
    bad = service.create_link(
        {"experiment_id": mismatching["id"], "dataset_version_id": v["id"], "role": "reference"}
    )
    assert ok["fingerprint_match"] is True
    assert bad["fingerprint_match"] is False


def test_link_requires_existing_records():
    d = _dataset()
    v = _version(d["id"])
    with pytest.raises(service.NotFoundError):
        service.create_link({"experiment_id": 999, "dataset_version_id": v["id"], "role": "input"})
    exp = exp_service.create_experiment(
        {"name": "E", "module": "m", "experiment_type": "t"}, source="test"
    )
    with pytest.raises(service.NotFoundError):
        service.create_link({"experiment_id": exp["id"], "dataset_version_id": 999, "role": "input"})


# ---------------------------------------------------------------------------
# Demo loader
# ---------------------------------------------------------------------------


def test_demo_seed_idempotent_and_preserves_user_data():
    user_ds = _dataset(name="User dataset")
    first = demo.seed_demo_lineage()
    assert first["created_datasets"] == 7
    assert first["created_versions"] == 8
    assert first["created_edges"] == 5
    second = demo.seed_demo_lineage()
    assert second["created_datasets"] == 0
    assert second["created_versions"] == 0
    assert second["created_edges"] == 0
    assert second["skipped_existing"] > 0
    # User record untouched; totals stable.
    assert service.get_dataset(user_ds["id"])["name"] == "User dataset"
    assert service.registry_summary()["datasets"] == 8  # 7 demo + 1 user


def test_demo_contains_warning_drift_invalidated_partial():
    demo.seed_demo_lineage()
    alt = store.get_dataset_by_name("Demo — Alt Sentiment Sample")
    assert alt is not None
    versions = {v["version_label"]: v for v in store.list_versions(alt["id"])}
    v1, v2 = versions["v1"], versions["v2"]
    assert v1["quality_status"] == "warning"
    assert v1["invalidated_at"] is not None
    cmp = service.compare_versions(v1["id"], v2["id"])
    assert cmp["drift_class"] in ("breaking", "potentially_breaking")
    # Dataset provenance is partial (v2 has source but no content fingerprint).
    assert service.get_dataset(alt["id"])["provenance_status"] == "partial"
