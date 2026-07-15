# Experiment Reproducibility Policy (Phase 48.0)

This document defines exactly what "reproducibility" means — and does **not**
mean — in the QuantLab Research Experiment Registry.

## What it means here

Reproducibility in the registry is **repository-level metadata validation**: a
conservative comparison of a candidate run's recorded metadata against a
reference run's recorded metadata (fingerprints, dataset identity, random seed,
provenance). It tells you whether two runs *claim* the same inputs and produced
the same recorded outputs.

## What it does NOT mean

It is **not**:

- a claim of scientific reproducibility,
- a re-execution or independent verification of the experiment,
- an audit trail or regulatory validation,
- a tamper-proof security control,
- a statement about model correctness, statistical validity, or investment merit.

A `reproducible` status means "the recorded metadata matches" — nothing more.

## Metadata requirements

A meaningful assessment needs, at minimum, a **configuration fingerprint** on
both the candidate and the reference. Richer signals (dataset fingerprint,
random seed, result fingerprint) sharpen the result. Missing metadata yields
`unknown` or `partially_reproducible`, never a false `reproducible`.

## Fingerprint interpretation

Fingerprints are deterministic SHA-256 digests over canonical JSON:

- **Configuration fingerprint** identifies the result-changing *inputs* (module,
  experiment type, parameters, random seed, dataset identity). It excludes
  timestamps, database ids, and display state, so it is stable across time and
  field order.
- **Result fingerprint** identifies the recorded *outputs* (metrics) bound to the
  configuration fingerprint.
- **Dataset fingerprint** identifies the data by a supplied verified hash or by a
  deterministic fixture's identity metadata.

Equal fingerprints mean equal canonical inputs/outputs. They do not prove the
underlying computation was correct.

## Dataset identity

Dataset identity is, in order of strength: a supplied SHA-256 `dataset_fingerprint`
(strongest), a fixture-identity-derived fingerprint, or the `dataset_name` alone
(weakest — "identity match by name only"). When only the name matches, the best
achievable status is `partially_reproducible`.

## Random seeds

For stochastic workflows, the seed is part of the configuration fingerprint. If
both runs record a seed and they differ, the configurations differ. A missing
seed on either side is treated as "not applicable" rather than a mismatch.

## Provenance

`git_commit` and `app_version` are captured best-effort (cached, local, never
network) and shown for context. They are informational in the assessment, not
decisive — a different commit does not by itself change the status.

## Deterministic vs stochastic workflows

- **Deterministic** (fixtures, frozen demos): the same configuration + dataset
  fingerprint must yield the same result fingerprint. If it does not, that is a
  strong `not_reproducible` signal (determinism broken).
- **Stochastic**: with a matching seed the run should be deterministic; without a
  recorded seed, differing results are expected and yield
  `partially_reproducible` rather than `not_reproducible`.

## The four states (conservative rules)

- **reproducible** — configuration matches, dataset fingerprint matches, seed
  matches when applicable, and the result fingerprint matches.
- **partially_reproducible** — configuration matches but the result differs (and
  the dataset could not be confirmed identical), or the dataset identity matches
  while its exact fingerprint is unavailable, or a result fingerprint is missing.
- **not_reproducible** — the configuration fingerprint differs, the dataset
  fingerprint/name differs, the required seed differs, or an identical
  configuration+dataset produced a materially different result fingerprint.
- **unknown** — insufficient metadata (no reference, or a missing configuration
  fingerprint).

The rules are returned in the assessment's `checks` array so the reasoning is
always visible.

## Fixture-regression policy

Deterministic fixtures (e.g. the KO/PEP pairs demo, Scenario Studio severe
stress) are expected to reproduce exactly. A demonstrated `not_reproducible`
result against a fixture baseline indicates the fixture, the code path, or the
recorded metadata changed — investigate before trusting the run. Frozen demo
values (119 trades, −23.0% vs +112.7%; severity 100/100, 8/8 modules) are never
edited to satisfy a comparison.

## Model-change policy

Changing a module's math, parameters, or dataset legitimately changes its
configuration and/or result fingerprint. That is expected and correct: mark a new
baseline for the new configuration rather than editing history. The registry
records what happened; it does not hide changes.
