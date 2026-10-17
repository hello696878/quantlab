# Deterministic Evidence-Grounded Research Explainer v1

Stored facts only. No advice, predictions, rankings, causal explanations,
new analytics, LLM/model calls, providers, credentials or explanation registry.
An inspection fingerprint is consistency evidence, not execution attestation.

## Source and Support Map

| Source | v1 support | Boundary |
| --- | --- | --- |
| Saved SMA, logical saved_backtests_row_v1 | Supported selected scalar/parameter/metric fields | Real existing save path; legacy facts explicitly unverified |
| Replay context replay_context_v1 / backtest_config_v1 | Internal recorded material/result/config/input/execution hashes checked | Existing verifier consumes the same pinned saved row, not a later reread |
| SMA context parameter projection | Fast/slow from /config/strategy_params when absent from saved params | References identify the context and original decoded snapshot path |
| Parent-linked replay contexts | Refused | No recursive cross-record acquisition or silent legacy fallback |
| RSI/Bollinger/momentum/breakout/pairs/custom/portfolio/research schemas | Unsupported, 422 | No automatic adapter substitution |
| Phase 65 lifecycle and dataset links | Explicitly unverified/unavailable in this adapter | No lifecycle registry reads, diagnostics, model-origin statement or atomic cross-registry claim |
| Benchmark, equity summaries, total trades | Deferred | No missing analytics derived; no count from possibly truncated lists |
| Scanner downloads | Unsupported | No scanner-import/persisted-run subsystem |

The schema name saved_backtests_row_v1 identifies this adapter's decoded-row
contract, not a historical execution attestation or a newly added DB column.
params_json/metrics_json/equity_curve_json/trades_json decode to the original
logical saved-result fields. JSON Pointer paths below address those decoded
fields; replay paths address the decoded snapshot_json. Evidence is a small
allowlisted projection, not a complete raw record. Names, notes, ticker labels,
CSV bytes, URLs, locators and environment/server paths never enter the export.

## Field, Unit and Wording Dictionary

All factual sentences start with a code-owned "The stored ..." prefix. Original
typed values and their display rule remain in each fact. Dates/counts are facts,
not exempt from provenance. Source IDs, material/context hashes and stored
creation time identify the pinned source outside the narrative.

| Original logical saved path | Unit / format | Interpretation |
| --- | --- | --- |
| /start_date, /end_date | ISO date / unchanged | Stored range labels, not inferred data/trading-day coverage |
| /initial_capital | USD / two decimals with grouping | USD follows the existing SavedBacktestCreate contract, not ticker inference |
| /transaction_cost_bps | one-way bps / two decimals | Stored per-side cost, not an invented realized fee |
| /params/fast_window, /params/slow_window | positive integer observations | Context fallback is explicitly bound to /config/strategy_params/fast_window or slow_window |
| /metrics/total_return, /metrics/cagr | decimal return / percentage | Presentation-only multiplication by 100; no recomputation |
| /metrics/max_drawdown | nonpositive decimal return / percentage | Sign preserved; positive drawdown refused |
| /metrics/volatility | nonnegative recorded annualized decimal / percentage | Negative values refuse; this adapter does not establish annualization convention or crypto suitability |
| /metrics/sharpe_ratio, /metrics/sortino_ratio, /metrics/calmar_ratio | ratio / four decimals | Descriptive stored number, not skill/significance/definedness proof |
| /metrics/win_rate | fraction of positive-return days / percentage | Existing metrics.compute_metrics definition, NOT fraction of profitable trades |
| /metrics/num_days | positive integer equity observations | Includes starting equity observation; not number of return periods or trading days |

Unknown/nonfinite/Boolean numeric values are never coerced to zero. Counts must
be actual positive integers; dates must be canonical ISO dates. Fractions stay
within [0,1], starting capital is positive, cost and volatility nonnegative. Tiny nonzero
values that would round to zero use scientific notation instead. Finite large
values remain grouped/readable within the existing safe JSON numeric bound.
Absent and null facts are separate states, distinct from available zero. Extra
metric availability/quality/unit declarations, including unfamiliar per-metric
spellings, are refused rather than overriding their meaning with a numeric
payload. Metrics use the closed nine-field dictionary; saved SMA params use the
existing save/replay producer keys. Context windows must be positive strict
integers and agree with overlapping saved values in both type and value.
Presentation uses a fixed local round-half-even Decimal context, independent of
ambient settings. No flag is fabricated for old stored results.
Stored fallback numbers do not establish that the underlying statistic was defined.

## Read-Only Acquisition and Identity

GET /research-explainer/saved-backtests/{id}, through the usual /api proxy,
accepts only a positive bounded integer ID and optional expected full SHA-256.
Unknown/duplicate/oversized queries refuse. No arbitrary source kind, pointer,
template, SQL, URL, filesystem locator or executable adapter input is accepted.
Responses are no-store. 404 means missing/unavailable source; 409 means relevant
source change or recorded integrity mismatch; 422 means unsupported/invalid
source/schema/fields or request. Public errors are bounded and do not echo inputs.

The narrow reader supports observed rollback-mode SQLite storage without
journal/WAL/SHM sidecars; WAL headers or any such sidecar refuse before connection.
This avoids the demonstrated creation of WAL/SHM files by a mode=ro WAL reader.
The preflight is not atomic protection against another process racing a path or
journal-mode change; no immutable live reader or incomplete WAL copy is used.
The reader uses SQLite mode=ro, query_only and one read transaction for
the saved row and optional context. It does not use get_connection, init_db,
migrations, writable registry helpers or current machine metadata collection.
A missing file/directory is not created. SQL IDs are parameterized. Only the
two relevant tables are discovered; aggregate lengths of all selected fields
are checked before loading, and context columns are explicitly selected.
The connection is closed before rendering; everything comes from that pinned
transaction. This is SQLite read-transaction consistency, not filesystem
immutability, a universal concurrency sandbox or an atomic cross-registry read.
Normal SQLite locking/WAL mechanics are not replaced by a custom VFS.

Selected saved material is bounded to 4 MiB, selected replay material to 512 KiB,
SQLite values to 5 MiB. A v1 lexical preflight bounds nesting depth, 300000 tokens
(including object keys), 100000 container entries, 512 KiB string tokens and
128-character scalar tokens before full decoding. These conservative bounds
may refuse material before the shared decoder's own structural limit. Strict
existing JSON validation then rejects duplicate keys and nonfinite/unsafe
numbers without changing unrelated legacy reads. The resulting explanation is
capped at 64 KiB, 20 facts and 40
statements. Fixed dictionaries actually emit 15 facts and 23 statements.
These bounds are defensive refusal rules, not a performance guarantee.

Existing Phase 66 result_identity covers actual selected result material,
including all decoded params/metrics/equity/trades; it excludes names/notes.
Database-local saved ID, stored creation time and optional context ID/schema/
snapshot/result/input/execution/configuration hashes prevent mistaking a shared
configuration hash for a unique saved execution. Legacy reproducibility metadata,
when present, must validate and agree with the saved row; incomplete/advertised
but missing replay indexes refuse. Corrupt context is never downgraded to legacy.
Legacy facts without context remain unverified even with a new inspection hash.
Optional links remain unverified, including when their material changes; no
model-origin assertion depends on them. The bundle identity binds context bytes,
but does not attest the current linked registry material. No locators are followed.

## Closed Contract and Policy

research_explanation_v1 uses saved_sma_v1, saved_sma_en_v1,
stored_facts_policy_v1 and fixed en-US locale. Same pinned material and versions
produce the same content/hash; no request timestamp or inspection environment
is mixed into stable content. Source bytes are not normalized for claim scanning.

Facts carry exact original path, source, raw typed value, unit, state, rule and
display. Statements carry the facts actually used or an explicit policy/template
ID. Missing-field wording is "This stored record does not provide...", never
"The engine never calculated...". Generic pointer handling implements RFC-style
slash/tilde escaping, missing members and bounded array indexing; public field
access remains a fixed allowlist, not a generic database browser.

Before returning, a separate validation pass checks the typed contract, closed
projection/identity fields, exact fact types/values/paths, closed statements and
content fingerprint. It rerenders approved templates and independently resolves
the original fact bindings. Rehashing modified wording/bindings does not make it
approved. Backend hash validation is not a signature or authenticity proof.

Code-owned templates and final sentences are checked for banned advice,
recommendations, predictions, persuasion, good/bad verdicts and unsupported
alpha/skill/robustness claims. Exact approved negative policy statements, such
as "not investment advice", are allowed; a disclaimer cannot license another
recommendation. Closed structure, not substring filtering alone, is the control.
Stored prose never selects templates or generates narrative. No HTML/Markdown
source rendering or eval/exec is added.

## Detail UI, Export and Later Browser Acceptance

Saved Backtest detail contains an explicit Explain stored result panel. Opening,
navigating or selecting records performs no explanation request or research.
Only the button requests the fixed read endpoint. It displays the pinned source
and trust scope, factual sentences, policy limitations and accessible Source
buttons opening the exact raw/display/unit/path/identity reference. There is no
navigation to external source URLs. Result selection/unmount tickets and a
synchronous busy ref prevent stale replacement and duplicate requests.

Check pinned source makes a fresh read using expected fingerprint; relevant
change/deletion refuses and detaches the displayed explanation. Without a fresh
check, the retained bundle explicitly describes only its pinned snapshot. Name/
note-only edits do not change scientific material identity. Download explanation
JSON validates references and preserves the exact validated response text bound
to the displayed object, including 0.0/-0.0 numeric tokens. Copied or modified
objects refuse; export does not refetch or reserialize against newer state.
No explanation persistence is added.

Synthetic acceptance uses the existing real save/read path and explicit fixture
engine execution BEFORE forbidden-work spies. The explanation itself never
executes it and does not require a profitable result. The focused browser spec
uses the actual Saved Backtests row View action and existing run_replay_e2e
harness. Both ownership proofs must pass THROUGH the actual frontend proxy
before demo writes. Use current user-selected ports/token; no old server or
token is assumed. Discovery is not execution. No services/browser/build start
is authorized by this implementation.

See [review evidence](PHASE_69_REVIEW.md) for the completed independent review,
fixes, exact current snapshots/failures and pending exact-review-commit Python
3.11 CI/user build/isolated browser gates. The unchanged
[implementation evidence](PHASE_69_IMPLEMENTATION.md) retains inherited runs.
Phase 68 remains frozen; Phase 70 is not implemented.
