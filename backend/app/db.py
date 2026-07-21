"""
SQLite database layer for QuantLab.

Design notes
------------
* Uses only the Python standard-library ``sqlite3`` module — no ORM required.
* ``get_db_path()`` honours a module-level override (``_db_path_override``) so
  tests can redirect all queries to a temporary file without touching the real
  database.
* ``init_db()`` is idempotent: ``CREATE TABLE IF NOT EXISTS`` makes it safe to
  call on every startup or in test fixtures.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Default database lives at  backend/data/quantlab.db
_DATA_DIR: Path = Path(__file__).parent.parent / "data"

# Set by tests (via monkeypatch) to redirect all queries to a temp file.
_db_path_override: Optional[Path] = None


def get_db_path() -> Path:
    """Return the active database path (override if set, else default)."""
    if _db_path_override is not None:
        return _db_path_override
    return _DATA_DIR / "quantlab.db"


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------


def get_connection() -> sqlite3.Connection:
    """
    Open and return a new SQLite connection.

    The parent directory of the database file is created automatically when it
    does not exist (covers the default ``backend/data/`` directory and any
    temporary directory used by tests).
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------


def init_db() -> None:
    """
    Create the application tables if they do not already exist.

    Safe to call multiple times (idempotent).  Called once at application
    startup and once per test via the ``fresh_db`` fixture.
    """
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_backtests (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at          TEXT    NOT NULL,
                name                TEXT    NOT NULL,
                ticker              TEXT    NOT NULL,
                strategy            TEXT    NOT NULL,
                start_date          TEXT    NOT NULL,
                end_date            TEXT    NOT NULL,
                initial_capital     REAL    NOT NULL,
                transaction_cost_bps REAL   NOT NULL,
                params_json         TEXT    NOT NULL DEFAULT '{}',
                metrics_json        TEXT    NOT NULL DEFAULT '{}',
                equity_curve_json   TEXT    NOT NULL DEFAULT '[]',
                trades_json         TEXT    NOT NULL DEFAULT '[]',
                notes               TEXT    NOT NULL DEFAULT ''
            )
            """
        )
        # Reusable Custom Strategy Builder definitions (NOT backtest results).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_strategy_templates (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL,
                name              TEXT NOT NULL,
                description       TEXT NOT NULL DEFAULT '',
                entry_logic       TEXT NOT NULL,
                exit_logic        TEXT NOT NULL,
                entry_rules_json  TEXT NOT NULL DEFAULT '[]',
                exit_rules_json   TEXT NOT NULL DEFAULT '[]',
                tags_json         TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        # Saved research reports (Report Gallery).  Stores the Markdown report
        # text + structured metadata only — never PDF binaries.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_reports (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL,
                title             TEXT NOT NULL,
                report_type       TEXT NOT NULL,
                source_type       TEXT NOT NULL,
                source_id         INTEGER,
                tickers_json      TEXT NOT NULL DEFAULT '[]',
                strategy          TEXT,
                date_range_start  TEXT,
                date_range_end    TEXT,
                markdown_content  TEXT NOT NULL,
                metadata_json     TEXT NOT NULL DEFAULT '{}',
                notes             TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Research Experiment Registry (Phase 48.0).  A local-first catalogue of
        # reproducibility metadata for research runs.  Structured fields that
        # genuinely vary (parameters, metrics, tags, provenance) are stored as
        # JSON text; everything used for filtering / sorting / relationships /
        # fingerprints / baseline selection is an explicit column.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiment_registry (
                id                         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at                 TEXT    NOT NULL,
                updated_at                 TEXT    NOT NULL,
                name                       TEXT    NOT NULL,
                description                TEXT    NOT NULL DEFAULT '',
                module                     TEXT    NOT NULL,
                experiment_type            TEXT    NOT NULL,
                status                     TEXT    NOT NULL,
                reproducibility_status     TEXT    NOT NULL DEFAULT 'unknown',
                started_at                 TEXT,
                completed_at               TEXT,
                duration_ms                INTEGER,
                git_commit                 TEXT,
                app_version                TEXT,
                dataset_name               TEXT,
                dataset_version            TEXT,
                dataset_fingerprint        TEXT,
                configuration_fingerprint  TEXT    NOT NULL,
                result_fingerprint         TEXT,
                random_seed                INTEGER,
                parameters_json            TEXT    NOT NULL DEFAULT '{}',
                metrics_json               TEXT    NOT NULL DEFAULT '{}',
                tags_json                  TEXT    NOT NULL DEFAULT '[]',
                provenance_json            TEXT    NOT NULL DEFAULT '{}',
                notes                      TEXT    NOT NULL DEFAULT '',
                parent_experiment_id       INTEGER
                                           REFERENCES experiment_registry(id),
                is_baseline                INTEGER NOT NULL DEFAULT 0,
                error_message              TEXT,
                demo_key                   TEXT
            )
            """
        )
        # Indexes for the registry's filter / sort / relationship / baseline
        # access paths.  All IF NOT EXISTS — safe to run on every startup.
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_created_at ON experiment_registry(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_module ON experiment_registry(module)",
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_type ON experiment_registry(experiment_type)",
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_status ON experiment_registry(status)",
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_repro ON experiment_registry(reproducibility_status)",
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_baseline ON experiment_registry(is_baseline)",
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_config_fp ON experiment_registry(configuration_fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_dataset_fp ON experiment_registry(dataset_fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_exp_reg_parent ON experiment_registry(parent_experiment_id)",
            # Unique demo_key makes demo-fixture loading idempotent while leaving
            # real records (demo_key IS NULL) unconstrained (SQLite treats NULLs
            # as distinct in a UNIQUE index).
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_exp_reg_demo_key ON experiment_registry(demo_key)",
        ):
            conn.execute(index_sql)
        # ------------------------------------------------------------------
        # Data Provenance & Dataset Lineage registry (Phase 49.0).
        # Dataset identity + immutable versions + lineage edges + quality
        # results + experiment links.  Filter/status/fingerprint fields are
        # explicit columns; only genuinely varying structures are JSON.
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at         TEXT    NOT NULL,
                updated_at         TEXT    NOT NULL,
                name               TEXT    NOT NULL,
                description        TEXT    NOT NULL DEFAULT '',
                domain             TEXT    NOT NULL,
                dataset_type       TEXT    NOT NULL,
                source_type        TEXT    NOT NULL,
                provider           TEXT,
                source_reference   TEXT,
                license_name       TEXT,
                license_url        TEXT,
                symbol_scope       TEXT,
                asset_class        TEXT,
                frequency          TEXT,
                timezone           TEXT,
                format             TEXT    NOT NULL,
                schema_version     TEXT,
                current_version_id INTEGER,
                tags_json          TEXT    NOT NULL DEFAULT '[]',
                metadata_json      TEXT    NOT NULL DEFAULT '{}',
                notes              TEXT    NOT NULL DEFAULT '',
                is_demo            INTEGER NOT NULL DEFAULT 0,
                is_active          INTEGER NOT NULL DEFAULT 1,
                provenance_status  TEXT    NOT NULL DEFAULT 'unknown',
                demo_key           TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_versions (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id           INTEGER NOT NULL REFERENCES datasets(id),
                version_label        TEXT    NOT NULL,
                created_at           TEXT    NOT NULL,
                effective_from       TEXT,
                effective_to         TEXT,
                row_count            INTEGER,
                column_count         INTEGER,
                start_time           TEXT,
                end_time             TEXT,
                content_fingerprint  TEXT,
                manifest_fingerprint TEXT    NOT NULL,
                schema_fingerprint   TEXT,
                source_fingerprint   TEXT,
                file_size_bytes      INTEGER,
                format               TEXT    NOT NULL,
                compression          TEXT,
                storage_locator_type TEXT    NOT NULL,
                storage_locator      TEXT    NOT NULL,
                ingestion_method     TEXT    NOT NULL DEFAULT 'manual',
                deterministic        INTEGER NOT NULL DEFAULT 0,
                quality_status       TEXT    NOT NULL DEFAULT 'unknown',
                validation_status    TEXT    NOT NULL DEFAULT 'unknown',
                schema_snapshot_json TEXT    NOT NULL DEFAULT '{}',
                statistics_json      TEXT    NOT NULL DEFAULT '{}',
                provenance_json      TEXT    NOT NULL DEFAULT '{}',
                invalidated_at       TEXT,
                invalidation_reason  TEXT,
                demo_key             TEXT,
                UNIQUE (dataset_id, version_label)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_lineage (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_version_id      INTEGER NOT NULL REFERENCES dataset_versions(id),
                child_version_id       INTEGER NOT NULL REFERENCES dataset_versions(id),
                relationship_type      TEXT    NOT NULL,
                transformation_name    TEXT    NOT NULL,
                transformation_version TEXT,
                parameters_json        TEXT    NOT NULL DEFAULT '{}',
                code_reference         TEXT,
                git_commit             TEXT,
                created_at             TEXT    NOT NULL,
                notes                  TEXT    NOT NULL DEFAULT '',
                UNIQUE (parent_version_id, child_version_id,
                        relationship_type, transformation_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_quality_results (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_version_id INTEGER NOT NULL REFERENCES dataset_versions(id),
                check_name         TEXT    NOT NULL,
                check_category     TEXT    NOT NULL,
                status             TEXT    NOT NULL,
                severity           TEXT    NOT NULL,
                observed_value     TEXT,
                expected_value     TEXT,
                message            TEXT    NOT NULL DEFAULT '',
                checked_at         TEXT    NOT NULL,
                checker_version    TEXT    NOT NULL,
                details_json       TEXT    NOT NULL DEFAULT '{}'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiment_dataset_links (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id      INTEGER NOT NULL REFERENCES experiment_registry(id),
                dataset_version_id INTEGER NOT NULL REFERENCES dataset_versions(id),
                role               TEXT    NOT NULL,
                created_at         TEXT    NOT NULL,
                notes              TEXT    NOT NULL DEFAULT '',
                UNIQUE (experiment_id, dataset_version_id, role)
            )
            """
        )
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_ds_source_type ON datasets(source_type)",
            "CREATE INDEX IF NOT EXISTS idx_ds_domain ON datasets(domain)",
            "CREATE INDEX IF NOT EXISTS idx_ds_provenance ON datasets(provenance_status)",
            "CREATE INDEX IF NOT EXISTS idx_ds_active ON datasets(is_active)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ds_demo_key ON datasets(demo_key)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ds_name ON datasets(name)",
            "CREATE INDEX IF NOT EXISTS idx_dsv_dataset ON dataset_versions(dataset_id)",
            "CREATE INDEX IF NOT EXISTS idx_dsv_quality ON dataset_versions(quality_status)",
            "CREATE INDEX IF NOT EXISTS idx_dsv_manifest_fp ON dataset_versions(manifest_fingerprint)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_dsv_demo_key ON dataset_versions(demo_key)",
            "CREATE INDEX IF NOT EXISTS idx_dsl_parent ON dataset_lineage(parent_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_dsl_child ON dataset_lineage(child_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_dsq_version ON dataset_quality_results(dataset_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_edl_experiment ON experiment_dataset_links(experiment_id)",
            "CREATE INDEX IF NOT EXISTS idx_edl_version ON experiment_dataset_links(dataset_version_id)",
        ):
            conn.execute(index_sql)
        # ------------------------------------------------------------------
        # Purged CV / CPCV Model Validation Lab (Phase 50.0).
        # Runs + per-split records.  Sample payloads and split memberships are
        # bounded validated JSON (≤ 2000 samples per run — documented in
        # docs/MODEL_VALIDATION_LAB.md §Persistence); everything used for
        # filtering / status / fingerprints / links is an explicit column.
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_runs (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at                TEXT    NOT NULL,
                updated_at                TEXT    NOT NULL,
                name                      TEXT    NOT NULL,
                description               TEXT    NOT NULL DEFAULT '',
                method                    TEXT    NOT NULL,
                status                    TEXT    NOT NULL DEFAULT 'pending',
                configuration_json        TEXT    NOT NULL DEFAULT '{}',
                samples_json              TEXT    NOT NULL DEFAULT '[]',
                configuration_fingerprint TEXT    NOT NULL,
                result_fingerprint        TEXT,
                sample_count              INTEGER NOT NULL DEFAULT 0,
                split_count               INTEGER NOT NULL DEFAULT 0,
                valid_split_count         INTEGER NOT NULL DEFAULT 0,
                invalid_split_count       INTEGER NOT NULL DEFAULT 0,
                leakage_clean             INTEGER,
                aggregate_metrics_json    TEXT    NOT NULL DEFAULT '{}',
                leakage_summary_json      TEXT    NOT NULL DEFAULT '{}',
                started_at                TEXT,
                completed_at              TEXT,
                duration_ms               INTEGER,
                experiment_id             INTEGER REFERENCES experiment_registry(id),
                dataset_version_id        INTEGER REFERENCES dataset_versions(id),
                random_seed               INTEGER,
                app_version               TEXT,
                git_commit                TEXT,
                is_baseline               INTEGER NOT NULL DEFAULT 0,
                notes                     TEXT    NOT NULL DEFAULT '',
                error_message             TEXT,
                demo_key                  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_splits (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                validation_run_id  INTEGER NOT NULL REFERENCES validation_runs(id),
                split_index        INTEGER NOT NULL,
                split_label        TEXT    NOT NULL,
                split_fingerprint  TEXT    NOT NULL,
                status             TEXT    NOT NULL,
                train_ids_json     TEXT    NOT NULL DEFAULT '[]',
                test_ids_json      TEXT    NOT NULL DEFAULT '[]',
                purged_ids_json    TEXT    NOT NULL DEFAULT '[]',
                embargoed_ids_json TEXT    NOT NULL DEFAULT '[]',
                diagnostics_json   TEXT    NOT NULL DEFAULT '{}',
                metrics_json       TEXT    NOT NULL DEFAULT '{}',
                UNIQUE (validation_run_id, split_index)
            )
            """
        )
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_vr_created ON validation_runs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_vr_method ON validation_runs(method)",
            "CREATE INDEX IF NOT EXISTS idx_vr_status ON validation_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_vr_experiment ON validation_runs(experiment_id)",
            "CREATE INDEX IF NOT EXISTS idx_vr_dataset ON validation_runs(dataset_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_vr_config_fp ON validation_runs(configuration_fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_vr_baseline ON validation_runs(is_baseline)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_vr_demo_key ON validation_runs(demo_key)",
            "CREATE INDEX IF NOT EXISTS idx_vs_run ON validation_splits(validation_run_id)",
        ):
            conn.execute(index_sql)
        # ------------------------------------------------------------------
        # Meta-Labeling / Calibration / Threshold Lab (Phase 51.0).
        # Observations and reliability bins are normalized rows (bounded:
        # ≤2000 observations per run — documented in docs/META_LABELING_LAB.md);
        # threshold analysis (≤101 grid rows) lives in run JSON.
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_label_runs (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at                TEXT    NOT NULL,
                updated_at                TEXT    NOT NULL,
                name                      TEXT    NOT NULL,
                description               TEXT    NOT NULL DEFAULT '',
                status                    TEXT    NOT NULL DEFAULT 'pending',
                label_policy_json         TEXT    NOT NULL DEFAULT '{}',
                calibration_method        TEXT    NOT NULL DEFAULT 'none',
                oof_status                TEXT    NOT NULL DEFAULT 'unknown',
                validation_run_id         INTEGER REFERENCES validation_runs(id),
                dataset_version_id        INTEGER REFERENCES dataset_versions(id),
                experiment_id             INTEGER REFERENCES experiment_registry(id),
                configuration_json        TEXT    NOT NULL DEFAULT '{}',
                configuration_fingerprint TEXT    NOT NULL,
                result_fingerprint        TEXT,
                observation_count         INTEGER NOT NULL DEFAULT 0,
                labeled_count             INTEGER NOT NULL DEFAULT 0,
                positive_count            INTEGER NOT NULL DEFAULT 0,
                abstained_count           INTEGER NOT NULL DEFAULT 0,
                raw_metrics_json          TEXT    NOT NULL DEFAULT '{}',
                calibrated_metrics_json   TEXT    NOT NULL DEFAULT '{}',
                calibration_params_json   TEXT    NOT NULL DEFAULT '{}',
                threshold_analysis_json   TEXT    NOT NULL DEFAULT '{}',
                completed_at              TEXT,
                duration_ms               INTEGER,
                app_version               TEXT,
                git_commit                TEXT,
                notes                     TEXT    NOT NULL DEFAULT '',
                error_message             TEXT,
                demo_key                  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta_label_observations (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id                 INTEGER NOT NULL REFERENCES meta_label_runs(id),
                sample_id              TEXT    NOT NULL,
                prediction_time        TEXT    NOT NULL,
                evaluation_time        TEXT    NOT NULL,
                primary_side           INTEGER NOT NULL,
                primary_score          REAL,
                raw_probability        REAL,
                calibrated_probability REAL,
                realized_outcome       REAL,
                meta_label             INTEGER,
                abstained              INTEGER NOT NULL DEFAULT 0,
                sample_weight          REAL,
                split_label            TEXT,
                metadata_json          TEXT    NOT NULL DEFAULT '{}',
                UNIQUE (run_id, sample_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calibration_bins (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id             INTEGER NOT NULL REFERENCES meta_label_runs(id),
                source             TEXT    NOT NULL,
                bin_index          INTEGER NOT NULL,
                lower_bound        REAL,
                upper_bound        REAL,
                sample_count       INTEGER NOT NULL,
                mean_probability   REAL,
                observed_frequency REAL,
                calibration_gap    REAL,
                UNIQUE (run_id, source, bin_index)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS threshold_policies (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at                TEXT    NOT NULL,
                updated_at                TEXT    NOT NULL,
                run_id                    INTEGER NOT NULL REFERENCES meta_label_runs(id),
                name                      TEXT    NOT NULL,
                threshold                 REAL    NOT NULL,
                abstention_json           TEXT,
                configuration_fingerprint TEXT    NOT NULL,
                observed_coverage         REAL,
                observed_precision        REAL,
                observed_recall           REAL,
                observed_f1               REAL,
                is_baseline               INTEGER NOT NULL DEFAULT 0,
                notes                     TEXT    NOT NULL DEFAULT ''
            )
            """
        )
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_mlr_created ON meta_label_runs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_mlr_status ON meta_label_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_mlr_method ON meta_label_runs(calibration_method)",
            "CREATE INDEX IF NOT EXISTS idx_mlr_oof ON meta_label_runs(oof_status)",
            "CREATE INDEX IF NOT EXISTS idx_mlr_vrun ON meta_label_runs(validation_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_mlr_dataset ON meta_label_runs(dataset_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_mlr_config_fp ON meta_label_runs(configuration_fingerprint)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_mlr_demo_key ON meta_label_runs(demo_key)",
            "CREATE INDEX IF NOT EXISTS idx_mlo_run ON meta_label_observations(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_cb_run ON calibration_bins(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_tp_run ON threshold_policies(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_tp_baseline ON threshold_policies(is_baseline)",
        ):
            conn.execute(index_sql)
        # ------------------------------------------------------------------
        # Feature Importance / Stability / Drift Diagnostics Lab (Phase 52.0).
        # Samples, aggregate + split-level results, correlation groups and
        # drift rows are normalized (bounded: ≤2000 samples, ≤32 features,
        # ≤20 permutation repeats per run — docs/FEATURE_DIAGNOSTICS_LAB.md);
        # stability summaries and split status lists live in bounded run JSON.
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_runs (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at                TEXT    NOT NULL,
                updated_at                TEXT    NOT NULL,
                name                      TEXT    NOT NULL,
                description               TEXT    NOT NULL DEFAULT '',
                status                    TEXT    NOT NULL DEFAULT 'pending',
                method                    TEXT    NOT NULL,
                model_type                TEXT    NOT NULL,
                target_type               TEXT    NOT NULL,
                metric                    TEXT    NOT NULL,
                metric_direction          TEXT    NOT NULL,
                split_source              TEXT    NOT NULL,
                integrity_status          TEXT    NOT NULL DEFAULT 'unknown',
                validation_run_id         INTEGER REFERENCES validation_runs(id),
                dataset_version_id        INTEGER REFERENCES dataset_versions(id),
                experiment_id             INTEGER REFERENCES experiment_registry(id),
                meta_label_run_id         INTEGER REFERENCES meta_label_runs(id),
                configuration_json        TEXT    NOT NULL DEFAULT '{}',
                configuration_fingerprint TEXT    NOT NULL,
                result_fingerprint        TEXT,
                baseline_fingerprint      TEXT,
                sample_count              INTEGER NOT NULL DEFAULT 0,
                feature_count             INTEGER NOT NULL DEFAULT 0,
                split_count               INTEGER NOT NULL DEFAULT 0,
                valid_split_count         INTEGER NOT NULL DEFAULT 0,
                invalid_split_count       INTEGER NOT NULL DEFAULT 0,
                splits_json               TEXT    NOT NULL DEFAULT '[]',
                stability_summary_json    TEXT    NOT NULL DEFAULT '{}',
                importance_drift_json     TEXT    NOT NULL DEFAULT '{}',
                references_json           TEXT    NOT NULL DEFAULT '{}',
                drift_context_json        TEXT    NOT NULL DEFAULT '{}',
                warnings_json             TEXT    NOT NULL DEFAULT '[]',
                is_baseline               INTEGER NOT NULL DEFAULT 0,
                baseline_scope            TEXT,
                completed_at              TEXT,
                duration_ms               INTEGER,
                app_version               TEXT,
                git_commit                TEXT,
                notes                     TEXT    NOT NULL DEFAULT '',
                error_message             TEXT,
                demo_key                  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_samples (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id        INTEGER NOT NULL REFERENCES feature_runs(id),
                sample_id     TEXT    NOT NULL,
                timestamp     TEXT    NOT NULL,
                target        REAL    NOT NULL,
                features_json TEXT    NOT NULL DEFAULT '{}',
                UNIQUE (run_id, sample_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_results (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id                  INTEGER NOT NULL REFERENCES feature_runs(id),
                feature_name            TEXT    NOT NULL,
                definition_json         TEXT    NOT NULL DEFAULT '{}',
                rank                    REAL,
                mean_importance         REAL,
                median_importance       REAL,
                std_importance          REAL,
                min_importance          REAL,
                max_importance          REAL,
                quantile_json           TEXT,
                mean_rank               REAL,
                median_rank             REAL,
                rank_std                REAL,
                rank_range              REAL,
                positive_split_fraction REAL,
                negative_split_fraction REAL,
                valid_split_count       INTEGER NOT NULL DEFAULT 0,
                stability_score         REAL,
                stability_classification TEXT   NOT NULL DEFAULT 'unknown',
                sign_consistency        REAL,
                sign_changed            INTEGER NOT NULL DEFAULT 0,
                warning                 TEXT,
                UNIQUE (run_id, feature_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_split_results (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id              INTEGER NOT NULL REFERENCES feature_runs(id),
                split_id            TEXT    NOT NULL,
                split_index         INTEGER NOT NULL,
                feature_name        TEXT    NOT NULL,
                baseline_score      REAL,
                mean_importance     REAL,
                median_importance   REAL,
                std_importance      REAL,
                min_importance      REAL,
                max_importance      REAL,
                positive_repeats    INTEGER NOT NULL DEFAULT 0,
                negative_repeats    INTEGER NOT NULL DEFAULT 0,
                valid_repeats       INTEGER NOT NULL DEFAULT 0,
                permutation_repeats INTEGER NOT NULL DEFAULT 0,
                rank                REAL,
                status              TEXT    NOT NULL DEFAULT 'ok',
                warning             TEXT,
                UNIQUE (run_id, split_id, feature_name)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_correlation_groups (
                id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id                   INTEGER NOT NULL REFERENCES feature_runs(id),
                group_id                 TEXT    NOT NULL,
                size                     INTEGER NOT NULL,
                max_abs_correlation      REAL,
                members_json             TEXT    NOT NULL DEFAULT '[]',
                pairs_json               TEXT    NOT NULL DEFAULT '[]',
                combined_mean_importance REAL,
                UNIQUE (run_id, group_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feature_drift_results (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id         INTEGER NOT NULL REFERENCES feature_runs(id),
                feature_name   TEXT    NOT NULL,
                kind           TEXT    NOT NULL,
                classification TEXT    NOT NULL DEFAULT 'unknown',
                psi            REAL,
                ks_statistic   REAL,
                detail_json    TEXT    NOT NULL DEFAULT '{}',
                UNIQUE (run_id, feature_name, kind)
            )
            """
        )
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_fr_created ON feature_runs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_fr_status ON feature_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_fr_method ON feature_runs(method)",
            "CREATE INDEX IF NOT EXISTS idx_fr_metric ON feature_runs(metric)",
            "CREATE INDEX IF NOT EXISTS idx_fr_integrity ON feature_runs(integrity_status)",
            "CREATE INDEX IF NOT EXISTS idx_fr_vrun ON feature_runs(validation_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_fr_dataset ON feature_runs(dataset_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_fr_config_fp ON feature_runs(configuration_fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_fr_baseline ON feature_runs(is_baseline)",
            "CREATE INDEX IF NOT EXISTS idx_fr_scope ON feature_runs(baseline_scope)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_fr_demo_key ON feature_runs(demo_key)",
            "CREATE INDEX IF NOT EXISTS idx_fs_run ON feature_samples(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_fres_run ON feature_results(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_fsr_run ON feature_split_results(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_fcg_run ON feature_correlation_groups(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_fdr_run ON feature_drift_results(run_id)",
        ):
            conn.execute(index_sql)
        # ------------------------------------------------------------------
        # Backtest Overfitting / PBO / Deflated Sharpe / Multiple Testing Lab
        # (Phase 53.0).  Candidates (with bounded return arrays ≤2000 obs),
        # CSCV split results (≤924 combinations) and multiple-testing rows are
        # normalized; aggregates/blocks/diagnostics live in bounded run JSON —
        # docs/BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md.
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS overfitting_diagnostic_runs (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at                TEXT    NOT NULL,
                updated_at                TEXT    NOT NULL,
                name                      TEXT    NOT NULL,
                description               TEXT    NOT NULL DEFAULT '',
                status                    TEXT    NOT NULL DEFAULT 'pending',
                metric                    TEXT    NOT NULL,
                block_count               INTEGER NOT NULL,
                candidate_count           INTEGER NOT NULL DEFAULT 0,
                observation_count         INTEGER NOT NULL DEFAULT 0,
                combination_count         INTEGER NOT NULL DEFAULT 0,
                valid_split_count         INTEGER NOT NULL DEFAULT 0,
                invalid_split_count       INTEGER NOT NULL DEFAULT 0,
                pbo_estimate              REAL,
                psr                       REAL,
                dsr                       REAL,
                benchmark_sharpe          REAL,
                effective_trial_count     REAL,
                universe_fingerprint      TEXT    NOT NULL,
                configuration_json        TEXT    NOT NULL DEFAULT '{}',
                configuration_fingerprint TEXT    NOT NULL,
                result_fingerprint        TEXT,
                timestamps_json           TEXT    NOT NULL DEFAULT '[]',
                blocks_json               TEXT    NOT NULL DEFAULT '[]',
                pbo_aggregate_json        TEXT    NOT NULL DEFAULT '{}',
                sharpe_diagnostics_json   TEXT    NOT NULL DEFAULT '{}',
                dependence_json           TEXT    NOT NULL DEFAULT '{}',
                warnings_json             TEXT    NOT NULL DEFAULT '[]',
                dataset_version_id        INTEGER REFERENCES dataset_versions(id),
                validation_run_id         INTEGER REFERENCES validation_runs(id),
                experiment_id             INTEGER REFERENCES experiment_registry(id),
                feature_diagnostics_run_id INTEGER REFERENCES feature_runs(id),
                is_baseline               INTEGER NOT NULL DEFAULT 0,
                baseline_scope            TEXT,
                completed_at              TEXT,
                duration_ms               INTEGER,
                app_version               TEXT,
                git_commit                TEXT,
                notes                     TEXT    NOT NULL DEFAULT '',
                error_message             TEXT,
                demo_key                  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS overfitting_candidates (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id                    INTEGER NOT NULL
                                          REFERENCES overfitting_diagnostic_runs(id),
                candidate_id              TEXT    NOT NULL,
                name                      TEXT    NOT NULL,
                description               TEXT    NOT NULL DEFAULT '',
                candidate_group           TEXT,
                experiment_id             INTEGER REFERENCES experiment_registry(id),
                validation_run_id         INTEGER REFERENCES validation_runs(id),
                dataset_version_id        INTEGER REFERENCES dataset_versions(id),
                configuration_fingerprint TEXT,
                result_fingerprint        TEXT,
                returns_json              TEXT    NOT NULL DEFAULT '[]',
                nominal_p_value           REAL,
                p_value_provenance_json   TEXT,
                metadata_json             TEXT    NOT NULL DEFAULT '{}',
                raw_sharpe                REAL,
                skewness                  REAL,
                kurtosis                  REAL,
                psr                       REAL,
                sharpe_status             TEXT,
                sharpe_note               TEXT,
                mean_return               REAL,
                cumulative_return         REAL,
                selection_frequency       REAL,
                mean_oos_rank             REAL,
                status                    TEXT    NOT NULL DEFAULT 'ok',
                UNIQUE (run_id, candidate_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pbo_split_results (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id                INTEGER NOT NULL
                                      REFERENCES overfitting_diagnostic_runs(id),
                split_id              TEXT    NOT NULL,
                split_index           INTEGER NOT NULL,
                is_block_ids_json     TEXT    NOT NULL DEFAULT '[]',
                oos_block_ids_json    TEXT    NOT NULL DEFAULT '[]',
                selected_candidate_id TEXT,
                is_metric             REAL,
                oos_metric            REAL,
                oos_rank              REAL,
                oos_defined_count     INTEGER,
                relative_rank         REAL,
                lambda                REAL,
                degradation           REAL,
                rank_degradation      REAL,
                tie_in_sample         INTEGER NOT NULL DEFAULT 0,
                tie_out_of_sample     INTEGER NOT NULL DEFAULT 0,
                status                TEXT    NOT NULL DEFAULT 'valid',
                warning               TEXT,
                UNIQUE (run_id, split_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS multiple_testing_results (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id             INTEGER NOT NULL
                                   REFERENCES overfitting_diagnostic_runs(id),
                candidate_id       TEXT    NOT NULL,
                raw_p_value        REAL,
                bonferroni         REAL,
                holm               REAL,
                bh                 REAL,
                provenance_status  TEXT    NOT NULL DEFAULT 'unavailable',
                provenance_json    TEXT,
                state_raw          TEXT    NOT NULL DEFAULT 'unavailable',
                state_bonferroni   TEXT    NOT NULL DEFAULT 'unavailable',
                state_holm         TEXT    NOT NULL DEFAULT 'unavailable',
                state_bh           TEXT    NOT NULL DEFAULT 'unavailable',
                UNIQUE (run_id, candidate_id)
            )
            """
        )
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_odr_created ON overfitting_diagnostic_runs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_odr_status ON overfitting_diagnostic_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_odr_metric ON overfitting_diagnostic_runs(metric)",
            "CREATE INDEX IF NOT EXISTS idx_odr_pbo ON overfitting_diagnostic_runs(pbo_estimate)",
            "CREATE INDEX IF NOT EXISTS idx_odr_dataset ON overfitting_diagnostic_runs(dataset_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_odr_vrun ON overfitting_diagnostic_runs(validation_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_odr_experiment ON overfitting_diagnostic_runs(experiment_id)",
            "CREATE INDEX IF NOT EXISTS idx_odr_config_fp ON overfitting_diagnostic_runs(configuration_fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_odr_universe_fp ON overfitting_diagnostic_runs(universe_fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_odr_baseline ON overfitting_diagnostic_runs(is_baseline)",
            "CREATE INDEX IF NOT EXISTS idx_odr_scope ON overfitting_diagnostic_runs(baseline_scope)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_odr_demo_key ON overfitting_diagnostic_runs(demo_key)",
            "CREATE INDEX IF NOT EXISTS idx_oc_run ON overfitting_candidates(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_psr_run ON pbo_split_results(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_mtr_run ON multiple_testing_results(run_id)",
        ):
            conn.execute(index_sql)
        # ------------------------------------------------------------------
        # Market Regime Robustness / Conditional Performance Lab (Phase 54.0).
        # Definitions carry their per-period effective-label arrays as bounded
        # JSON (≤2000 periods, ≤6 definitions — the documented v1 form of the
        # regime_assignments entity); conditional results are explicit rows;
        # robustness/rank/concentration/coverage summaries live in bounded run
        # JSON — docs/REGIME_DIAGNOSTICS_LAB.md.
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS regime_diagnostic_runs (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at                TEXT    NOT NULL,
                updated_at                TEXT    NOT NULL,
                name                      TEXT    NOT NULL,
                description               TEXT    NOT NULL DEFAULT '',
                status                    TEXT    NOT NULL DEFAULT 'pending',
                candidate_count           INTEGER NOT NULL DEFAULT 0,
                observation_count         INTEGER NOT NULL DEFAULT 0,
                period_count              INTEGER NOT NULL DEFAULT 0,
                frequency                 TEXT    NOT NULL DEFAULT '',
                regime_definition_count   INTEGER NOT NULL DEFAULT 0,
                observed_regime_count     INTEGER NOT NULL DEFAULT 0,
                invalid_definition_count  INTEGER NOT NULL DEFAULT 0,
                low_coverage_warning_count INTEGER NOT NULL DEFAULT 0,
                integrity_status          TEXT    NOT NULL DEFAULT 'unknown',
                universe_fingerprint      TEXT    NOT NULL,
                configuration_json        TEXT    NOT NULL DEFAULT '{}',
                configuration_fingerprint TEXT    NOT NULL,
                result_fingerprint        TEXT,
                timestamps_json           TEXT    NOT NULL DEFAULT '[]',
                candidates_json           TEXT    NOT NULL DEFAULT '[]',
                market_features_json      TEXT    NOT NULL DEFAULT '{}',
                sample_ids_json           TEXT,
                coverage_json             TEXT    NOT NULL DEFAULT '{}',
                robustness_json           TEXT    NOT NULL DEFAULT '[]',
                rank_stability_json       TEXT    NOT NULL DEFAULT '{}',
                concentration_json        TEXT    NOT NULL DEFAULT '[]',
                warnings_json             TEXT    NOT NULL DEFAULT '[]',
                dataset_version_id        INTEGER REFERENCES dataset_versions(id),
                validation_run_id         INTEGER REFERENCES validation_runs(id),
                overfitting_run_id        INTEGER
                                          REFERENCES overfitting_diagnostic_runs(id),
                feature_diagnostics_run_id INTEGER REFERENCES feature_runs(id),
                meta_label_run_id         INTEGER REFERENCES meta_label_runs(id),
                experiment_id             INTEGER REFERENCES experiment_registry(id),
                is_baseline               INTEGER NOT NULL DEFAULT 0,
                baseline_scope            TEXT,
                completed_at              TEXT,
                duration_ms               INTEGER,
                app_version               TEXT,
                git_commit                TEXT,
                notes                     TEXT    NOT NULL DEFAULT '',
                error_message             TEXT,
                demo_key                  TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS regime_definitions (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id                INTEGER NOT NULL
                                      REFERENCES regime_diagnostic_runs(id),
                definition_id         TEXT    NOT NULL,
                name                  TEXT    NOT NULL,
                description           TEXT    NOT NULL DEFAULT '',
                dimension             TEXT    NOT NULL,
                source_feature        TEXT,
                lookback              INTEGER,
                lag                   INTEGER,
                threshold_mode        TEXT,
                min_observations      INTEGER NOT NULL DEFAULT 8,
                integrity_status      TEXT    NOT NULL DEFAULT 'unknown',
                status                TEXT    NOT NULL DEFAULT 'pending',
                definition_json       TEXT    NOT NULL DEFAULT '{}',
                definition_fingerprint TEXT   NOT NULL,
                thresholds_used_json  TEXT,
                threshold_fingerprint TEXT,
                assignments_json      TEXT    NOT NULL DEFAULT '[]',
                unavailable_count     INTEGER NOT NULL DEFAULT 0,
                distinct_label_count  INTEGER NOT NULL DEFAULT 0,
                interval_summary_json TEXT    NOT NULL DEFAULT '{}',
                transition_json       TEXT    NOT NULL DEFAULT '{}',
                warnings_json         TEXT    NOT NULL DEFAULT '[]',
                UNIQUE (run_id, definition_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS regime_conditional_results (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id              INTEGER NOT NULL
                                    REFERENCES regime_diagnostic_runs(id),
                candidate_id        TEXT    NOT NULL,
                definition_id       TEXT    NOT NULL,
                regime_label        TEXT    NOT NULL,
                observation_count   INTEGER NOT NULL DEFAULT 0,
                coverage            REAL,
                mean                REAL,
                median              REAL,
                std                 REAL,
                minimum             REAL,
                maximum             REAL,
                positive_rate       REAL,
                negative_rate       REAL,
                cumulative          REAL,
                sharpe_like         REAL,
                downside_deviation  REAL,
                status              TEXT    NOT NULL DEFAULT 'ok',
                note                TEXT,
                UNIQUE (run_id, candidate_id, definition_id, regime_label)
            )
            """
        )
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_rdr_created ON regime_diagnostic_runs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_rdr_status ON regime_diagnostic_runs(status)",
            "CREATE INDEX IF NOT EXISTS idx_rdr_integrity ON regime_diagnostic_runs(integrity_status)",
            "CREATE INDEX IF NOT EXISTS idx_rdr_dataset ON regime_diagnostic_runs(dataset_version_id)",
            "CREATE INDEX IF NOT EXISTS idx_rdr_vrun ON regime_diagnostic_runs(validation_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_rdr_orun ON regime_diagnostic_runs(overfitting_run_id)",
            "CREATE INDEX IF NOT EXISTS idx_rdr_config_fp ON regime_diagnostic_runs(configuration_fingerprint)",
            "CREATE INDEX IF NOT EXISTS idx_rdr_baseline ON regime_diagnostic_runs(is_baseline)",
            "CREATE INDEX IF NOT EXISTS idx_rdr_scope ON regime_diagnostic_runs(baseline_scope)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_rdr_demo_key ON regime_diagnostic_runs(demo_key)",
            "CREATE INDEX IF NOT EXISTS idx_rd_run ON regime_definitions(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_rcr_run ON regime_conditional_results(run_id)",
            "CREATE INDEX IF NOT EXISTS idx_rcr_candidate ON regime_conditional_results(run_id, candidate_id)",
        ):
            conn.execute(index_sql)
        conn.commit()
    finally:
        conn.close()
