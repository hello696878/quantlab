"""
Deterministic synthetic ES raw-futures generator (Phase 6 — commit 1).

``generate_synthetic_es_raw(config)`` builds a multi-contract raw-futures frame in
the canonical Phase 1 schema, ready for ``validate_raw_futures`` and the continuous
builder.  It is **synthetic, not a download**: no network, no file I/O.

Construction (deterministic for a given seed):

* ``n_contracts`` consecutive in-cycle ES contracts (H/M/U/Z) starting from the
  first cycle expiry after ``start_date``;
* each contract trades a trailing block of ``sessions_per_contract`` business days
  ending on its (third-Friday) expiry — larger than one quarter, so consecutive
  contracts overlap and the days-before-expiry fallback roll always resolves;
* each contract sits at a base price ``base_price + i * contract_gap`` (so
  ``close_raw`` gaps ~``contract_gap`` at each seam while ratio adjustment stays
  smooth), with a per-session ``daily_drift`` and optional seeded ``noise_scale``;
* ``open_interest`` is ``None`` so the roll schedule uses the deterministic
  days-before-expiry fallback rather than a volume/OI crossover.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.instruments import CME_MONTH_CODES, get_instrument, third_friday


def _cycle_contracts(spec, start_date, n_contracts):
    """Return the first ``n_contracts`` in-cycle (symbol, expiry) slots after start."""
    cycle_codes = sorted(spec.contract_months, key=lambda c: CME_MONTH_CODES[c])
    slots = []
    year = start_date.year
    while len(slots) < n_contracts + len(cycle_codes):  # generate a margin, then trim
        for code in cycle_codes:
            expiry = third_friday(year, CME_MONTH_CODES[code])
            if expiry > start_date:
                slots.append((spec.build_contract_symbol(code, year), expiry))
        year += 1
    slots.sort(key=lambda s: s[1])
    return slots[:n_contracts]


def generate_synthetic_es_raw(config) -> pd.DataFrame:
    """Build a deterministic synthetic raw-futures frame (Phase 1 schema).

    Accepts an ``ExperimentConfig`` (uses its ``.synthetic``) or a
    ``SyntheticDataConfig`` directly.  Never writes files or touches the network."""
    syn = getattr(config, "synthetic", config)
    spec = get_instrument(syn.root_symbol)
    rng = np.random.default_rng(syn.random_seed)

    rows = []
    for i, (symbol, expiry) in enumerate(_cycle_contracts(spec, syn.start_date, syn.n_contracts)):
        sessions = pd.bdate_range(end=pd.Timestamp(expiry), periods=syn.sessions_per_contract)
        base = syn.base_price + i * syn.contract_gap
        for t, session in enumerate(sessions):
            noise = float(rng.normal(0.0, syn.noise_scale)) if syn.noise_scale > 0 else 0.0
            open_ = base + syn.daily_drift * t + noise
            close = open_ + 1.0
            rows.append(
                {
                    "timestamp": pd.Timestamp(session),
                    "open": open_,
                    "high": max(open_, close) + 1.0,
                    "low": min(open_, close) - 1.0,
                    "close": close,
                    "volume": int(syn.volume) + t,
                    "open_interest": None,  # -> deterministic days-before-expiry fallback roll
                    "root_symbol": syn.root_symbol,
                    "contract_symbol": symbol,
                    "expiry": pd.Timestamp(expiry),
                    "source": "synthetic",
                    "timezone": "America/Chicago",
                }
            )
    return pd.DataFrame(rows)
