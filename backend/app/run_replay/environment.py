"""Allowlisted context, with unknowns rather than machine-inventory inference."""
import platform
import subprocess
import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .identity import digest, validate

FIELDS = ("python", "pandas", "numpy", "fastapi", "pydantic", "scipy", "app_version", "git_commit", "source_dirty", "node", "frontend_build")


def collect(classification):
    fields = {key: None for key in FIELDS}
    fields["python"] = platform.python_version()
    for package in ("pandas", "numpy", "fastapi", "pydantic", "scipy"):
        try:
            fields[package] = version(package)
        except PackageNotFoundError:
            pass
    root = Path(__file__).resolve().parents[3]
    try:
        fields["app_version"] = (root / "VERSION").read_text(encoding="utf-8").strip()
        # A protected test snapshot deliberately has no Git metadata.
        if (root / ".git").exists():
            for key, args in (("git_commit", ["rev-parse", "HEAD"]), ("source_dirty", ["status", "--porcelain", "--untracked-files=normal"])):
                result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    fields[key] = bool(result.stdout.strip()) if key == "source_dirty" else result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return {"schema_version": "environment_manifest_v1", "classification": classification,
            "collection": "backend_local_allowlist", "fields": fields}


def check(manifest):
    validate(manifest, limit=8192)
    if set(manifest) != {"schema_version", "classification", "collection", "fields"} or manifest["schema_version"] != "environment_manifest_v1":
        raise ValueError("Unsupported environment manifest")
    if manifest["classification"] != "execution" or manifest["collection"] != "backend_local_allowlist":
        raise ValueError("Only declared execution manifests may describe execution")
    fields = manifest["fields"]
    if type(fields) is not dict or set(fields) != set(FIELDS):
        raise ValueError("Environment fields must match the allowlist")
    for key, value in fields.items():
        if value is None:
            continue
        if key == "source_dirty":
            if type(value) is not bool:
                raise ValueError("source_dirty must be Boolean or unknown")
        elif type(value) is not str or not re.fullmatch(r"[0-9A-Za-z.+_-]{1,100}", value):
            raise ValueError("Environment versions must be bounded strings")
        elif key == "git_commit" and not re.fullmatch(r"[a-f0-9]{40,64}", value):
            raise ValueError("Source commit must be a Git hash or unknown")
    return manifest


def compare(recorded, current):
    old = recorded["fields"] if recorded else {}
    return [{"field": key, "recorded": old.get(key), "current": current["fields"].get(key),
             "state": "unknown" if old.get(key) is None or current["fields"].get(key) is None else
             "same" if old[key] == current["fields"][key] else "different"} for key in FIELDS]


def capture(request, provenance="validated_model_with_defaults"):
    return {"schema_version": "replay_capture_v1", "original_request": request,
            "request_provenance": provenance, "execution_environment": collect("execution")}
