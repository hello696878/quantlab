# Factor Definition and Transformation Policy (v1)

Phase 59.0 · `backend/app/factor_diagnostics/definitions.py` and
`observations.py`

A factor definition is an explicit contract. **Nothing is inferred from a
factor's name**: an unrecognised factor stays `custom_descriptive`, an
unrecognised unit is a validation error, and an unrecognised transformation
is a validation error. There are no user-supplied expressions or formulas of
any kind — the transformation is chosen from a closed list.

## 1. Definition fields

| field | contract |
| --- | --- |
| `factor_id` | lowercase `[a-z0-9][a-z0-9_-]{0,63}`, unique within the run; the declared order is the design-matrix column order |
| `name`, `description` | free text, bounded (200 / 1000 chars) |
| `category` | `market`, `style`, `sector`, `volatility`, `liquidity`, `macro`, `custom_descriptive` — never assigned automatically |
| `source` | free text identity of where the series came from (bounded) |
| `unit` | source unit of the RAW series: `return_fraction`, `return_percent`, `basis_points`, `index_level`, `rate_fraction`, `rate_percent`, `zscore`, `ratio`, `count` |
| `frequency` | `daily` … `annual`, or `unspecified` |
| `transformation` | one of the eight below |
| `transformed_unit` | derived, not overridable (except for `supplied_transformed`, where it must be declared from the bounded unit vocabulary) |
| `lag` | integer in `[0, 60]`; **negative lags are rejected** |
| `availability_policy` | `same_timestamp`, `explicit_available_at`, `lagged_by_periods` |
| `missing_policy` | `unavailable` only — v1 never forward-fills, interpolates or zero-fills |
| `standardisation_policy` | `none` or `trailing_zscore` (requires a window) |
| `standardisation_window` | 3–500 observations; only valid with a trailing policy — a bare window is an error, and there is no centred option |
| `winsorisation_policy` | `none` only — see §4 |
| `dataset_version_id` | optional Dataset Lineage identity |

Bounds: at most **12 factors** per run and **2000 observations** per factor.

## 2. Transformation formulas

`x` is the raw source series, `v` the transformed series. The first `d`
values of a differencing or trailing transform are **unavailable** and are
never zero-filled or back-filled.

| transformation | formula | d | resulting unit |
| --- | --- | --- | --- |
| `level` | `v_t = x_t` | 0 | source unit |
| `simple_return` | `v_t = x_t / x_{t-1} − 1` | 1 | `return_fraction` |
| `percent_change` | `v_t = 100 · (x_t / x_{t-1} − 1)` | 1 | `return_percent` |
| `log_change` | `v_t = ln(x_t / x_{t-1})` | 1 | `log_change_fraction` |
| `first_difference` | `v_t = x_t − x_{t-1}` | 1 | `<unit>_change` |
| `basis_point_change` | `v_t = (x_t − x_{t-1}) · s` | 1 | `basis_points` |
| `trailing_zscore` | `v_t = (x_t − mean(x_{t−w..t−1})) / sd(x_{t−w..t−1})` | w | `zscore` |
| `supplied_transformed` | `v_t = x_t` | 0 | declared by the caller |

`s = 10 000` for a `rate_fraction` source and `100` for a `rate_percent`
source; `basis_point_change` is **rejected** for any other source unit, so
the conversion is never ambiguous. `log_change` requires both adjacent levels to be strictly positive. A `supplied_transformed` unit is validated against the same bounded source/change unit vocabulary, so a typo cannot create an apparently valid unit. `simple_return`, `percent_change` and
`log_change` require an `index_level`, `ratio` or `count` source — a ratio
of two rates is not a return.

## 3. The trailing z-score never sees itself or the future

The window ends one observation **before** `t`:

```
window = x[t−w … t−1]        (exclusive of t)
sd     = sample standard deviation, ddof = 1
```

A zero or non-finite trailing standard deviation leaves that observation
unavailable rather than producing a division artefact. A test asserts that
changing a **later** observation cannot change an earlier standardised
value.

## 4. Winsorisation is deferred

Only `winsorisation_policy: "none"` is accepted in v1, and the reason is
stated rather than hidden: any quantile threshold computed over the full
sample is look-ahead, and a trailing-quantile variant is not needed by any
v1 analysis mode. Nothing is clipped silently.

## 5. Observations

| field | contract |
| --- | --- |
| `observation_id` | unique across the run (auto-generated when omitted) |
| `source_timestamp` | ISO-8601; **strictly increasing** per factor |
| `available_at` | when the value could have been known; required when the policy is `explicit_available_at`; must not precede `source_timestamp` |
| `value` | finite, or `null` for an explicit gap |
| `vintages` | optional ordered releases, see [`MACRO_SENSITIVITY_AND_VINTAGE_POLICY.md`](MACRO_SENSITIVITY_AND_VINTAGE_POLICY.md) |
| `quality_state` | `observed`, `revised`, `estimated_by_source`, `unknown` |
| `metadata` | bounded object (at most 20 keys and 2000 rendered characters) |

ISO timestamps are calendar-validated and canonicalised before ordering and fingerprinting. Duplicate observation ids anywhere in the run, duplicate or out-of-order timestamps, non-finite
values and an `available_at` earlier than the observation it describes are
all validation errors.

## 6. Alignment

A target period is matched to the factor observation at the same timestamp
in the **factor's own** observation sequence, offset by the declared lag:

```
observation_index = index_of(period_start) − lag  (+ lead, only under the
                                                   declared-invalid policy)
```

Indexing in the factor's own sequence means a factor that carries history
**before** the target window can satisfy a lag — or a differencing
transform — at the very first target period instead of losing it.

If the factor has no observation at a target timestamp, the run is
**refused**: v1 aligns by exact timestamp and never resamples. If the
offset observation does not exist or its transformed value is unavailable,
that period leaves the estimation sample with its reason recorded.

Every factor frequency must equal the target return frequency; v1 refuses mixed-frequency regression rather than resampling.

## 7. Units and contributions

An exposure multiplied by a factor **return** is a return. Only
`return_fraction` (×1), `return_percent` (×0.01) and `basis_points` (×1e-4)
qualify; `supplied_exposure_aggregation` therefore refuses any other
transformed unit rather than producing a number whose unit nobody can state.
In `time_series_regression` the coefficient itself carries the unit, and the
UI prints it as *target return per 1 &lt;transformed unit&gt;*.
