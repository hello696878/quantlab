"""
Deterministic demo lineage for the Dataset Lineage registry.

Loaded only through an explicit action (``POST /datasets/demo-seed`` or the
frontend button) — never silently at startup.  Idempotent via unique
``demo_key`` values on datasets and versions; re-seeding creates nothing new
and never overwrites or deletes real records.

Three chains:

* **Scenario Studio** — raw macro fixture → normalized macro factors →
  severe cross-asset scenario inputs → linked to the Scenario Studio demo
  experiment.
* **KO/PEP Pairs** — raw price fixture → aligned prices → spread/z-score
  features → linked to the KO/PEP demo experiment.
* **Alt-data sample** — v1 (invalidated, quality warning, partial provenance)
  and v2 with deliberate schema drift, linked to the failed demo experiment.

Where safe, the Experiment Registry demo records are seeded first (their own
idempotent loader) so links have real targets.  Content fingerprints here are
computed from deterministic fixture identity payloads at seed time — an
explicit operation, never a per-request file hash.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.dataset_registry import service, store
from app.dataset_registry.fingerprints import sha256_hex
from app.experiment_registry.demo import seed_demo_registry as seed_experiment_demo
from app.experiment_registry.store import get_id_by_demo_key as experiment_id_by_key

_T0 = "2026-01-05T09:00:00Z"

_MACRO_SCHEMA = {
    "fields": [
        {"name": "date", "type": "date", "nullable": False},
        {"name": "gdp_growth", "type": "float", "nullable": True},
        {"name": "cpi_yoy", "type": "float", "nullable": True},
        {"name": "policy_rate", "type": "float", "nullable": False},
    ],
    "ordering_significant": False,
}
_FACTOR_SCHEMA = {
    "fields": [
        {"name": "date", "type": "date", "nullable": False},
        {"name": "growth_z", "type": "float", "nullable": False},
        {"name": "inflation_z", "type": "float", "nullable": False},
        {"name": "policy_z", "type": "float", "nullable": False},
    ],
    "ordering_significant": False,
}
_SCENARIO_SCHEMA = {
    "fields": [
        {"name": "module", "type": "string", "nullable": False},
        {"name": "shock", "type": "float", "nullable": False},
        {"name": "weight", "type": "float", "nullable": False},
    ],
    "ordering_significant": False,
}
_PRICE_SCHEMA = {
    "fields": [
        {"name": "date", "type": "date", "nullable": False},
        {"name": "ko_close", "type": "float", "nullable": False},
        {"name": "pep_close", "type": "float", "nullable": False},
    ],
    "ordering_significant": False,
}
_FEATURE_SCHEMA = {
    "fields": [
        {"name": "date", "type": "date", "nullable": False},
        {"name": "spread", "type": "float", "nullable": False},
        {"name": "zscore", "type": "float", "nullable": False},
    ],
    "ordering_significant": False,
}
_ALT_SCHEMA_V1 = {
    "fields": [
        {"name": "date", "type": "date", "nullable": False},
        {"name": "sentiment", "type": "float", "nullable": True},
    ],
    "ordering_significant": False,
}
_ALT_SCHEMA_V2 = {
    "fields": [
        {"name": "date", "type": "date", "nullable": False},
        {"name": "sentiment_score", "type": "float", "nullable": True},
        {"name": "source_count", "type": "integer", "nullable": False},
    ],
    "ordering_significant": False,
}


def _content_fp(identity: Dict[str, Any]) -> str:
    """Deterministic demo content fingerprint from a fixture identity payload."""
    return sha256_hex({"demo_fixture_identity": identity})


def _ensure_dataset(demo_key: str, payload: Dict[str, Any]) -> int:
    existing = store.dataset_demo_key_id(demo_key)
    if existing is not None:
        return existing
    return service.create_dataset(payload, demo_key=demo_key)["id"]


def _ensure_version(
    demo_key: str, dataset_id: int, payload: Dict[str, Any]
) -> tuple[int, bool]:
    existing = store.version_demo_key_id(demo_key)
    if existing is not None:
        return existing, False
    return service.create_version(dataset_id, payload, demo_key=demo_key)["id"], True


def seed_demo_lineage() -> Dict[str, int]:
    """Idempotently load the demo datasets, versions, lineage, quality, links."""
    created_datasets = created_versions = created_edges = 0
    created_quality = created_links = 0
    skipped = 0

    # Experiment demo records first (their loader is idempotent too).
    seed_experiment_demo()

    def dataset(demo_key: str, **payload: Any) -> int:
        nonlocal created_datasets, skipped
        before = store.dataset_demo_key_id(demo_key)
        ds_id = _ensure_dataset(demo_key, payload)
        if before is None:
            created_datasets += 1
        else:
            skipped += 1
        return ds_id

    def version(demo_key: str, ds_id: int, **payload: Any) -> int:
        nonlocal created_versions, skipped
        vid, was_created = _ensure_version(demo_key, ds_id, payload)
        if was_created:
            created_versions += 1
        else:
            skipped += 1
        return vid

    def edge(parent: int, child: int, rel: str, name: str, params: Optional[Dict[str, Any]] = None) -> None:
        nonlocal created_edges, skipped
        before = store.find_identical_edge(
            {
                "parent_version_id": parent,
                "child_version_id": child,
                "relationship_type": rel,
                "transformation_name": name,
            }
        )
        service.add_lineage(
            {
                "parent_version_id": parent,
                "child_version_id": child,
                "relationship_type": rel,
                "transformation_name": name,
                "transformation_version": "v1",
                "parameters": params or {},
                "code_reference": None,
                "notes": "demo lineage",
            }
        )
        if before is None:
            created_edges += 1
        else:
            skipped += 1

    def link(exp_key: str, version_id: int, role: str) -> None:
        nonlocal created_links, skipped
        exp_id = experiment_id_by_key(exp_key)
        if exp_id is None:
            return
        before = store.find_link(exp_id, version_id, role)
        service.create_link(
            {"experiment_id": exp_id, "dataset_version_id": version_id, "role": role, "notes": "demo link"}
        )
        if before is None:
            created_links += 1
        else:
            skipped += 1

    # ── Scenario Studio chain ────────────────────────────────────────────
    ds_macro = dataset(
        "demo:ds:macro-raw",
        name="Demo — Raw Macro Fixture",
        description="Deterministic raw macro indicator fixture (demo).",
        domain="macro",
        dataset_type="indicators",
        source_type="deterministic_fixture",
        format="csv",
        frequency="monthly",
        timezone="UTC",
        schema_version="v1",
        tags=["demo", "scenario-studio"],
        is_demo=True,
    )
    v_macro = version(
        "demo:dsv:macro-raw:v1",
        ds_macro,
        version_label="v1",
        row_count=240,
        column_count=4,
        start_time="2006-01-01T00:00:00Z",
        end_time="2025-12-01T00:00:00Z",
        format="csv",
        storage_locator="fixture://scenario/macro-raw/v1",
        ingestion_method="fixture",
        deterministic=True,
        content_fingerprint=_content_fp({"fixture": "macro-raw", "rows": 240}),
        schema_snapshot=_MACRO_SCHEMA,
        statistics_summary={"missing_ratio": 0.0, "duplicate_ratio": 0.0},
        provenance={"source": "quantlab deterministic fixture", "created": _T0},
    )
    ds_factors = dataset(
        "demo:ds:macro-factors",
        name="Demo — Normalized Macro Factors",
        description="Z-scored macro factors derived from the raw fixture (demo).",
        domain="macro",
        dataset_type="features",
        source_type="derived",
        format="parquet",
        frequency="monthly",
        timezone="UTC",
        schema_version="v1",
        tags=["demo", "scenario-studio"],
        is_demo=True,
    )
    v_factors = version(
        "demo:dsv:macro-factors:v1",
        ds_factors,
        version_label="v1",
        row_count=240,
        column_count=4,
        start_time="2006-01-01T00:00:00Z",
        end_time="2025-12-01T00:00:00Z",
        format="parquet",
        storage_locator="generated://scenario/macro-factors/v1",
        ingestion_method="transform",
        deterministic=True,
        content_fingerprint=_content_fp({"fixture": "macro-factors", "rows": 240}),
        schema_snapshot=_FACTOR_SCHEMA,
        statistics_summary={"missing_ratio": 0.0, "duplicate_ratio": 0.0},
        provenance={"source": "derived from demo:dsv:macro-raw:v1", "created": _T0},
    )
    ds_scenario = dataset(
        "demo:ds:scenario-inputs",
        name="Demo — Severe Cross-Asset Scenario Inputs",
        description="Module shock/weight table for the severe stress combo (demo).",
        domain="scenario",
        dataset_type="scenario_inputs",
        source_type="derived",
        format="json",
        schema_version="v1",
        tags=["demo", "scenario-studio"],
        is_demo=True,
    )
    v_scenario = version(
        "demo:dsv:scenario-inputs:v1",
        ds_scenario,
        version_label="v1",
        row_count=8,
        column_count=3,
        format="json",
        storage_locator="fixture://scenario/severe-cross-asset/v1",
        ingestion_method="transform",
        deterministic=True,
        content_fingerprint=_content_fp({"fixture": "severe-scenario", "modules": 8}),
        schema_snapshot=_SCENARIO_SCHEMA,
        statistics_summary={"missing_ratio": 0.0},
        provenance={"source": "derived from demo:dsv:macro-factors:v1", "created": _T0},
    )
    edge(v_macro, v_factors, "normalized_from", "macro_zscore_normalization",
         {"window": 120})
    edge(v_factors, v_scenario, "derived_from", "severe_scenario_builder",
         {"scenario": "severe_cross_asset_stress_combo"})
    link("demo:scenario-studio:severe:baseline", v_scenario, "input")

    # ── KO/PEP chain ─────────────────────────────────────────────────────
    ds_prices = dataset(
        "demo:ds:kopep-raw",
        name="Demo — Raw KO/PEP Price Fixture",
        description="Deterministic KO/PEP daily close fixture (demo).",
        domain="equities",
        dataset_type="prices",
        source_type="deterministic_fixture",
        format="csv",
        frequency="daily",
        timezone="America/New_York",
        asset_class="equity",
        symbol_scope="KO, PEP",
        schema_version="v1",
        tags=["demo", "pairs", "ko-pep"],
        is_demo=True,
    )
    v_prices = version(
        "demo:dsv:kopep-raw:v1",
        ds_prices,
        version_label="v1",
        row_count=2515,
        column_count=3,
        start_time="2016-07-11T00:00:00Z",
        end_time="2026-07-11T00:00:00Z",
        format="csv",
        storage_locator="fixture://pairs/ko-pep/v1",
        ingestion_method="fixture",
        deterministic=True,
        content_fingerprint=_content_fp({"fixture": "ko_pep_pairs", "rows": 2515}),
        schema_snapshot=_PRICE_SCHEMA,
        statistics_summary={"missing_ratio": 0.0, "duplicate_ratio": 0.0},
        provenance={"source": "quantlab deterministic fixture", "created": _T0},
    )
    ds_aligned = dataset(
        "demo:ds:kopep-aligned",
        name="Demo — Aligned KO/PEP Prices",
        description="Calendar-aligned KO/PEP closes (demo).",
        domain="equities",
        dataset_type="prices",
        source_type="derived",
        format="parquet",
        frequency="daily",
        timezone="America/New_York",
        asset_class="equity",
        schema_version="v1",
        tags=["demo", "pairs"],
        is_demo=True,
    )
    v_aligned = version(
        "demo:dsv:kopep-aligned:v1",
        ds_aligned,
        version_label="v1",
        row_count=2515,
        column_count=3,
        start_time="2016-07-11T00:00:00Z",
        end_time="2026-07-11T00:00:00Z",
        format="parquet",
        storage_locator="generated://pairs/ko-pep-aligned/v1",
        ingestion_method="transform",
        deterministic=True,
        content_fingerprint=_content_fp({"fixture": "ko_pep_aligned", "rows": 2515}),
        schema_snapshot=_PRICE_SCHEMA,
        statistics_summary={"missing_ratio": 0.0, "duplicate_ratio": 0.0},
        provenance={"source": "derived from demo:dsv:kopep-raw:v1", "created": _T0},
    )
    ds_features = dataset(
        "demo:ds:kopep-features",
        name="Demo — KO/PEP Spread & Z-Score Features",
        description="Spread and rolling z-score features for the pairs demo (demo).",
        domain="equities",
        dataset_type="features",
        source_type="derived",
        format="parquet",
        frequency="daily",
        schema_version="v1",
        tags=["demo", "pairs", "features"],
        is_demo=True,
    )
    v_features = version(
        "demo:dsv:kopep-features:v1",
        ds_features,
        version_label="v1",
        row_count=2455,
        column_count=3,
        start_time="2016-10-03T00:00:00Z",
        end_time="2026-07-11T00:00:00Z",
        format="parquet",
        storage_locator="generated://pairs/ko-pep-features/v1",
        ingestion_method="transform",
        deterministic=True,
        content_fingerprint=_content_fp({"fixture": "ko_pep_features", "rows": 2455}),
        schema_snapshot=_FEATURE_SCHEMA,
        statistics_summary={"missing_ratio": 0.0, "duplicate_ratio": 0.0},
        provenance={"source": "derived from demo:dsv:kopep-aligned:v1", "created": _T0},
    )
    edge(v_prices, v_aligned, "normalized_from", "calendar_alignment", {"calendar": "NYSE"})
    edge(v_aligned, v_features, "feature_generated_from", "spread_zscore_features",
         {"lookback": 60})
    link("demo:kopep:pairs:baseline", v_features, "features")
    link("demo:kopep:pairs:baseline", v_prices, "input")

    # ── Alt-data example: warning + drift + invalidated + partial ────────
    ds_alt = dataset(
        "demo:ds:alt-sentiment",
        name="Demo — Alt Sentiment Sample",
        description="Hand-written sentiment sample demonstrating quality warnings, "
        "schema drift, and an invalidated version (demo).",
        domain="alternative_data",
        dataset_type="signals",
        source_type="manual",
        format="csv",
        frequency="daily",
        schema_version="v2",
        tags=["demo", "alt-data"],
        is_demo=True,
    )
    v_alt1_created = store.version_demo_key_id("demo:dsv:alt-sentiment:v1") is None
    v_alt1 = version(
        "demo:dsv:alt-sentiment:v1",
        ds_alt,
        version_label="v1",
        row_count=120,
        column_count=2,
        start_time="2025-09-01T00:00:00Z",
        end_time="2025-12-31T00:00:00Z",
        format="csv",
        storage_locator="local-file://alt_sentiment_sample.csv",
        ingestion_method="manual",
        deterministic=False,
        schema_snapshot=_ALT_SCHEMA_V1,
        statistics_summary={"missing_ratio": 0.12, "duplicate_ratio": 0.0},
        provenance={},  # deliberately partial/unknown
    )
    v_alt2 = version(
        "demo:dsv:alt-sentiment:v2",
        ds_alt,
        version_label="v2",
        row_count=180,
        column_count=3,
        start_time="2025-09-01T00:00:00Z",
        end_time="2026-01-31T00:00:00Z",
        format="csv",
        storage_locator="local-file://alt_sentiment_sample_v2.csv",
        ingestion_method="manual",
        deterministic=False,
        schema_snapshot=_ALT_SCHEMA_V2,
        statistics_summary={"missing_ratio": 0.02, "duplicate_ratio": 0.0},
        provenance={"source": "manual sample rebuild"},
    )
    edge(v_alt1, v_alt2, "copied_from", "manual_rebuild_with_new_schema", {})
    link("demo:alt-data:failed", v_alt1, "input")

    if v_alt1_created:
        # Quality run (missing_ratio 0.12 > 0.05 default → warning) and
        # invalidation — only on first creation so re-seeding stays a no-op.
        results = service.run_quality_checks(
            v_alt1,
            {"checks": ["row_count_nonzero", "missing_ratio_within_limit",
                        "content_fingerprint_present", "source_identity_present"],
             "expectations": {}},
        )
        created_quality += len(results)
        service.invalidate_version(
            v_alt1, "superseded by v2 after a schema rebuild (demo)"
        )
        results2 = service.run_quality_checks(
            v_alt2,
            {"checks": ["row_count_nonzero", "missing_ratio_within_limit",
                        "date_range_valid"], "expectations": {}},
        )
        created_quality += len(results2)

    return {
        "created_datasets": created_datasets,
        "created_versions": created_versions,
        "created_edges": created_edges,
        "created_quality_results": created_quality,
        "created_links": created_links,
        "skipped_existing": skipped,
    }


__all__ = ["seed_demo_lineage"]
