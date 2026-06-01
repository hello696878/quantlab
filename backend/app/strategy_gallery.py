"""
Built-in Strategy Template Gallery.

Curated, read-only custom strategy definitions exposed via
GET /custom-strategy-gallery.  These are *static Python data* — never stored in
SQLite — and are constructed through the same validated ``GalleryTemplate`` /
``CustomRule`` schema as user templates.  Construction happens at import time,
so a malformed built-in template fails immediately (and is caught by tests).

Security: there is no code execution.  Operands are plain data objects
(close / constant / whitelisted indicator); no formula strings exist.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.schemas import GalleryTemplate


# ---------------------------------------------------------------------------
# Tiny builders to keep the definitions readable
# ---------------------------------------------------------------------------


def _sma(window: int) -> dict:
    return {"type": "indicator", "name": "sma", "params": {"window": window}}


def _rsi(window: int) -> dict:
    return {"type": "indicator", "name": "rsi", "params": {"window": window}}


def _momentum(window: int) -> dict:
    return {"type": "indicator", "name": "momentum", "params": {"window": window}}


def _bb(name: str, window: int, num_std: Optional[float] = None) -> dict:
    params: dict = {"window": window}
    if num_std is not None:
        params["num_std"] = num_std
    return {"type": "indicator", "name": name, "params": params}


def _close() -> dict:
    return {"type": "close"}


def _const(value: float) -> dict:
    return {"type": "constant", "value": value}


def _rule(left: dict, operator: str, right: dict) -> dict:
    return {"left": left, "operator": operator, "right": right}


# ---------------------------------------------------------------------------
# Built-in template definitions
# ---------------------------------------------------------------------------

_RAW_TEMPLATES: List[dict] = [
    {
        "id": "sma-trend-filter",
        "name": "SMA Trend Filter",
        "description": "Long when the short-term trend is above the long-term trend.",
        "entry_logic": "AND",
        "exit_logic": "OR",
        "entry_rules": [_rule(_sma(50), ">", _sma(200))],
        "exit_rules": [_rule(_sma(50), "<", _sma(200))],
        "tags": ["trend", "moving-average", "simple"],
        "difficulty": "beginner",
        "category": "trend",
    },
    {
        "id": "rsi-mean-reversion",
        "name": "RSI Mean Reversion",
        "description": "Buy oversold conditions and exit after the bounce recovers.",
        "entry_logic": "AND",
        "exit_logic": "OR",
        "entry_rules": [_rule(_rsi(14), "<", _const(30))],
        "exit_rules": [_rule(_rsi(14), ">", _const(50))],
        "tags": ["mean-reversion", "rsi"],
        "difficulty": "beginner",
        "category": "mean_reversion",
    },
    {
        "id": "momentum-trend",
        "name": "Momentum + Trend",
        "description": (
            "Long only when medium-term momentum is positive and the long-term "
            "trend is supportive."
        ),
        "entry_logic": "AND",
        "exit_logic": "OR",
        "entry_rules": [
            _rule(_momentum(126), ">", _const(0)),
            _rule(_sma(50), ">", _sma(200)),
        ],
        "exit_rules": [
            _rule(_momentum(126), "<=", _const(0)),
            _rule(_sma(50), "<", _sma(200)),
        ],
        "tags": ["momentum", "trend"],
        "difficulty": "intermediate",
        "category": "momentum",
    },
    {
        "id": "bollinger-mean-reversion",
        "name": "Bollinger Mean Reversion",
        "description": (
            "Buy when price breaks below the lower Bollinger Band and exit at "
            "the middle band."
        ),
        "entry_logic": "AND",
        "exit_logic": "OR",
        "entry_rules": [_rule(_close(), "<", _bb("bb_lower", 20, 2.0))],
        "exit_rules": [_rule(_close(), ">", _bb("bb_middle", 20))],
        "tags": ["mean-reversion", "bollinger"],
        "difficulty": "intermediate",
        "category": "mean_reversion",
    },
    {
        "id": "defensive-trend",
        "name": "Defensive Trend Strategy",
        "description": (
            "A conservative trend-following rule using a long-term moving average."
        ),
        "entry_logic": "AND",
        "exit_logic": "OR",
        "entry_rules": [_rule(_close(), ">", _sma(200))],
        "exit_rules": [_rule(_close(), "<", _sma(200))],
        "tags": ["defensive", "trend", "long-term"],
        "difficulty": "beginner",
        "category": "trend",
    },
]


# Construct (and thereby validate) every built-in template at import time.
GALLERY: List[GalleryTemplate] = [GalleryTemplate(**t) for t in _RAW_TEMPLATES]

# Guard against accidental duplicate ids.
_BY_ID: Dict[str, GalleryTemplate] = {}
for _t in GALLERY:
    if _t.id in _BY_ID:
        raise ValueError(f"Duplicate gallery template id: {_t.id!r}")
    _BY_ID[_t.id] = _t


def list_gallery() -> List[GalleryTemplate]:
    """Return all built-in gallery templates (full definitions)."""
    return [template.model_copy(deep=True) for template in GALLERY]


def get_gallery_template(template_id: str) -> Optional[GalleryTemplate]:
    """Return one built-in template by id, or None if not found."""
    template = _BY_ID.get(template_id)
    return template.model_copy(deep=True) if template is not None else None
