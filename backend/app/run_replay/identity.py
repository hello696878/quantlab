"""Bounded plain JSON and identities independent of legacy canonicalization."""
import hashlib
import json
import math
import re

MAX_JSON = 4 * 1024 * 1024
MAX_CSV = 128 * 1024


def validate(value, *, limit=MAX_JSON):
    nodes = 0

    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if depth > 20 or nodes > 300000:
            raise ValueError("JSON exceeds depth or node bound")
        if item is None or type(item) is bool:
            return
        if type(item) is str:
            if len(item.encode("utf-8")) > 512 * 1024:
                raise ValueError("JSON string exceeds bound")
        elif type(item) in (int, float):
            if not math.isfinite(item) or abs(item) > 2**53 - 1:
                raise ValueError("JSON numbers must be finite and safely representable")
        elif type(item) is list:
            for child in item:
                visit(child, depth + 1)
        elif type(item) is dict:
            for key, child in item.items():
                if type(key) is not str or len(key) > 200:
                    raise ValueError("JSON keys must be bounded strings")
                visit(child, depth + 1)
        else:
            raise ValueError("Only plain JSON values are accepted")
    visit(value, 0)
    encoded = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > limit:
        raise ValueError("JSON exceeds size bound")
    return encoded


def loads(raw, *, limit=MAX_JSON):
    if len(raw if isinstance(raw, bytes) else raw.encode("utf-8")) > limit:
        raise ValueError("JSON exceeds size bound")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON keys are not allowed")
            result[key] = value
        return result
    try:
        result = json.loads(raw, object_pairs_hook=pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
        validate(result, limit=limit)
        return result
    except (RecursionError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or excessively nested JSON") from exc


def digest(value):
    return hashlib.sha256(validate(value).encode("utf-8")).hexdigest()


def full_hash(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Use the full lowercase 64-character SHA-256, not its display prefix")
    return value


def legacy(repro):
    from app.reproducibility import canonical_json, compute_config_hash
    if type(repro) is not dict or set(repro) != {"schema_version", "config_hash", "config_hash_full", "canonical_config_json"}:
        raise ValueError("Incomplete reproducibility record")
    config = loads(repro["canonical_config_json"], limit=32768)
    short, full = compute_config_hash(config)
    if full_hash(repro["config_hash_full"]) != full or repro["config_hash"] != short:
        raise ValueError("Canonical content does not match the advertised hash")
    if config.get("schema_version") != repro["schema_version"]:
        raise ValueError("Configuration schema mismatch")
    if canonical_json(config) != repro["canonical_config_json"]:
        raise ValueError("Stored configuration is not canonical")
    return config
