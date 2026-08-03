# Signal Universe and Alignment Policy (Phase 61, v1)

## 1. The universe contract

A signal universe is an explicit list of 2–12 signals, each a full Phase
60 signal-definition contract (reused, not duplicated): declared type,
unit, frequency, direction (**never inferred from a name**), availability
policy, tie policy and transformation. The universe adds:

* deterministic canonical ordering — signal ids are sorted, and every
  pairwise row, matrix axis and stored child row follows that order;
* unique signal ids (duplicates are refused);
* one shared stored frequency — mixed frequencies are refused because
  nothing is resampled to force compatibility;
* bounds: ≤ 50 entities, ≤ 40 000 observations across signals, ≤ 10 000
  aligned (entity, timestamp) keys;
* no automatic sign inversion, no silent unit conversion, no silent
  transformation, and no user-supplied code or expressions of any kind.

Orientation (`as_supplied` / `multiply_by_negative_one`) is a per-signal
user declaration applied to raw values before normalisation; the raw
stored values remain unchanged, the inversion is visibly disclosed, and
it is never derived from IC, bucket returns or any historical
performance. An inverted signal is never called corrected or improved.

## 2. Alignment keys

Signals align on explicit keys only:

```
(entity_id, timestamp)
```

with each observation's own availability timestamp carried alongside.
Row-number alignment is impossible by construction: shifting one
signal's timestamps changes the intersection instead of silently pairing
unrelated rows.

## 3. The two alignment policies

* **`strict_intersection`** (default) — only keys where EVERY signal in
  the universe has a stored, non-null value. This is the only universe
  that combination calculations, matrix-level diagnostics (eigenvalues,
  effective count, clustering) and regime/validation conditioning may
  use, so every matrix cell shares one observation universe.
* **`pairwise_complete`** — for pairwise diagnostics only: each pair
  uses its own overlap and every row carries its own sample count.
  Pairwise-complete rows are stored NEXT TO the strict rows, and a
  pairwise-complete matrix is never assembled — a matrix whose cells
  used different universes would silently mix samples.

## 4. Missingness is disclosed, never repaired

A missing observation is missing: no forward fill, no interpolation, no
fabricated observation, no zero imputation, no mean imputation. The
missingness summary (per signal: union keys, present, stored-null,
absent, coverage; plus the strict-intersection coverage) is part of the
result and visible in the UI. The alignment policy and missing policy
both enter the similarity-policy and universe fingerprints.

## 5. Bounded overlap honesty

A pair whose overlap is below the configured minimum (default 4,
explicit) is unavailable with the overlap count on the row. Thin overlap
is a fact about the data, and no statistic is fabricated to cover it.
