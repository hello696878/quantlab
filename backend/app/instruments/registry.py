"""
Instrument registry (Phase 1 — instrument spec layer).

Loads YAML specs from ``configs/instruments/`` into validated, immutable spec
objects.  Single source of truth for instrument metadata.  No data access.

V1 deliberately does not cache: spec files are tiny and loading on demand keeps
behaviour obvious and tests hermetic.  An ``lru_cache`` can be added later.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.instruments.base import (
    AssetClass,
    InstrumentError,
    InstrumentSpec,
    UnknownInstrumentError,
)
from app.instruments.futures import FuturesSpec

_FUTURES_CLASSES = {
    AssetClass.EQUITY_INDEX_FUTURE,
    AssetClass.COMMODITY_FUTURE,
    AssetClass.FX_FUTURE,
    AssetClass.RATES_FUTURE,
}


def default_instruments_dir() -> Path:
    """Repo-root ``configs/instruments`` directory (independent of cwd)."""
    # registry.py -> instruments -> app -> backend -> <repo root>
    return Path(__file__).resolve().parents[3] / "configs" / "instruments"


def _spec_path(root: str, instruments_dir: Path | None) -> Path:
    base = instruments_dir or default_instruments_dir()
    return base / f"{root.lower()}.yaml"


def load_spec(path: Path) -> InstrumentSpec:
    """Load and validate one spec file. Raises on malformed/invalid specs."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise InstrumentError(f"{path} did not parse to a mapping")
    try:
        ac = AssetClass(raw.get("asset_class"))
    except ValueError:
        # Unknown/invalid asset_class: hand to the strict base model so it raises
        # a precise ValidationError rather than us silently picking a model.
        return InstrumentSpec(**raw)
    model = FuturesSpec if ac in _FUTURES_CLASSES else InstrumentSpec
    return model(**raw)


def get_instrument(root: str, instruments_dir: Path | None = None) -> InstrumentSpec:
    """Return the validated spec for ``root`` (e.g. ``"ES"``)."""
    path = _spec_path(root, instruments_dir)
    if not path.exists():
        available = list_instruments(instruments_dir)
        raise UnknownInstrumentError(
            f"Unknown instrument {root!r} (no spec at {path}). "
            f"Available: {available or '[none]'}"
        )
    return load_spec(path)


def list_instruments(instruments_dir: Path | None = None) -> list[str]:
    """Return the sorted root symbols that have a spec file."""
    base = instruments_dir or default_instruments_dir()
    if not base.exists():
        return []
    return sorted(p.stem.upper() for p in base.glob("*.yaml"))
