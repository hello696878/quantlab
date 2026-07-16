"""
Dataset fingerprints: schema and manifest, over the shared canonical JSON.

Reuses the Experiment Registry's canonicalization (sorted keys, whole-float
normalization, **NaN/Infinity rejected**, unsupported types rejected) so both
registries hash identically-shaped inputs identically.

* **Schema fingerprint** — field names, normalized types, nullable flags, the
  ordering policy when it is meaningful, and the schema version.  No
  timestamps, no database ids.
* **Manifest fingerprint** — the dataset identity + version label + row/column
  counts + date range + format + schema fingerprint + source fingerprint +
  deterministic flag + declared provenance inputs.  No database ids, no
  absolute paths (locators are validated logical URIs before they get here).
* **Content fingerprint** — never computed by this module during API calls; it
  is either supplied (a verified SHA-256) or produced by an explicit fixture /
  test operation.  Large files are never hashed on a list/detail request.

Fingerprints are integrity aids — not digital signatures, not proof of
authorship, not tamper-proof guarantees, not certification.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from app.experiment_registry.fingerprints import (
    FingerprintError,
    canonical_json,
    is_valid_sha256,
    sha256_hex,
    short_hash,
)

SCHEMA_FP_VERSION = "dataset_schema_v1"
MANIFEST_FP_VERSION = "dataset_manifest_v1"

# Normalized type vocabulary; free-form types are lowercased/stripped.
_TYPE_ALIASES = {
    "int": "integer",
    "int64": "integer",
    "int32": "integer",
    "bigint": "integer",
    "double": "float",
    "float64": "float",
    "float32": "float",
    "real": "float",
    "numeric": "float",
    "str": "string",
    "text": "string",
    "varchar": "string",
    "bool": "boolean",
    "datetime64[ns]": "datetime",
    "timestamp": "datetime",
    "date64": "date",
}


def normalize_field_type(raw: str) -> str:
    t = str(raw).strip().lower()
    return _TYPE_ALIASES.get(t, t)


def canonical_schema(
    fields: Sequence[Mapping[str, Any]],
    *,
    ordering_significant: bool = False,
    schema_version: Optional[str] = None,
) -> dict:
    """Build the canonical schema payload from field descriptors.

    Each field is ``{"name": str, "type": str, "nullable": bool}``.  When
    ordering is not significant, fields are sorted by name so declaration
    order never changes the hash.
    """
    canon = []
    for f in fields:
        name = str(f.get("name", "")).strip()
        if not name:
            raise FingerprintError("schema field requires a non-empty name")
        canon.append(
            {
                "name": name,
                "type": normalize_field_type(f.get("type", "unknown")),
                "nullable": bool(f.get("nullable", True)),
            }
        )
    if not ordering_significant:
        canon.sort(key=lambda f: f["name"])
    return {
        "fp_version": SCHEMA_FP_VERSION,
        "ordering_significant": bool(ordering_significant),
        "schema_version": schema_version,
        "fields": canon,
    }


def schema_fingerprint(
    fields: Sequence[Mapping[str, Any]],
    *,
    ordering_significant: bool = False,
    schema_version: Optional[str] = None,
) -> str:
    return sha256_hex(
        canonical_schema(
            fields,
            ordering_significant=ordering_significant,
            schema_version=schema_version,
        )
    )


def manifest_fingerprint(
    *,
    dataset_name: str,
    version_label: str,
    row_count: Optional[int],
    column_count: Optional[int],
    start_time: Optional[str],
    end_time: Optional[str],
    fmt: str,
    schema_fp: Optional[str],
    source_fingerprint: Optional[str],
    deterministic: bool,
    provenance_inputs: Optional[Mapping[str, Any]] = None,
) -> str:
    payload = {
        "fp_version": MANIFEST_FP_VERSION,
        "dataset_name": dataset_name,
        "version_label": version_label,
        "row_count": row_count,
        "column_count": column_count,
        "date_range": {"start": start_time, "end": end_time},
        "format": fmt,
        "schema_fingerprint": schema_fp,
        "source_fingerprint": source_fingerprint,
        "deterministic": bool(deterministic),
        "provenance_inputs": dict(provenance_inputs or {}),
    }
    return sha256_hex(payload)


__all__ = [
    "SCHEMA_FP_VERSION",
    "MANIFEST_FP_VERSION",
    "FingerprintError",
    "canonical_json",
    "sha256_hex",
    "short_hash",
    "is_valid_sha256",
    "normalize_field_type",
    "canonical_schema",
    "schema_fingerprint",
    "manifest_fingerprint",
]
