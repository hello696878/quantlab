"""
AFML Methodology Layer v1 — a small, reusable **financial-ML methodology toolkit**
(inspired by *Advances in Financial Machine Learning*), exposed as the AFML
Methodology Lab.

It demonstrates the *labeling pipeline* that must come **before** model training:

1. **CUSUM event sampling** — sample events only when cumulative movement is large.
2. **Triple-barrier labeling** — label each event by which barrier (profit-take /
   stop-loss / vertical) is touched first.
3. **Sample concurrency** — count overlapping label intervals.
4. **Sample uniqueness weights** — down-weight overlapping (non-independent) labels.
5. **Purged K-fold + embargo CV** — remove train labels that overlap each
   contiguous test fold, then embargo post-test observations and report leakage.
6. **Sequential bootstrap** — sample events with probabilities driven by their
   uniqueness under the already-selected sample.

Educational / research only — **synthetic demo data**, no live market data, no
model training, no meta-labeling, no fractional differentiation, and no
Combinatorial Purged CV (all planned). **Not** a full AFML implementation and
not investment advice.
"""

from app.finml.orchestrator import (  # noqa: F401
    FinmlInputError,
    run_labeling_demo,
    validate_finml_inputs,
)
from app.finml.cv import (  # noqa: F401
    run_purged_cv_demo,
    validate_cv_inputs,
)
from app.finml.bootstrap import (  # noqa: F401
    run_sequential_bootstrap_demo,
    validate_bootstrap_inputs,
)
