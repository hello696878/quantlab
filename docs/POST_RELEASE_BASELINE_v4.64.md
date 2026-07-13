# Post-Release Stable Baseline — v4.64 (Phase 47.0)

The exact stable baseline from which future QuantLab development continues.
The baseline anchor is the **verified tag**, independent of the (still
pending) GitHub Release publication.

## Stable baseline identity

| Field | Value |
|---|---|
| Release tag | `v4.64.0-public-github-release-launch-v1` (local = remote) |
| Release commit | `2d4bcfeb218dfee758b908032eef198e305fbc4f` — "Add public GitHub release launch closure v1" (2026-07-12) |
| main HEAD at verification | `2d4bcfe` (identical to the tag target; clean tree at phase start) |
| Branch | `main` |
| VERSION | `4.65.0-dev` after this phase (was `4.64.0-dev` at the tag) |
| Predecessor tags | v4.63 → `47bfec0` · v4.62 → `f2d8831` · v4.61 → `32c8f35` · v4.60 → `7cf9708` (frozen) |
| CI evidence at baseline | CI run 29188597089 ✅ · Browser E2E Preflight run 29193708980 ✅ (both on `2d4bcfe`) |

## Protected behavior (regression surface — change deliberately or not at all)

The frozen public demo route · the five frozen screenshots
(`docs/screenshots/release_*.png`) · the Scenario Studio deterministic
severe-stress workflow · the KO/PEP deterministic pairs fixture · the
command palette (Ctrl+K) · Saved Reports behavior (empty and populated) ·
the responsive 1440/1024/768 paths · the 12-test Browser E2E suite
(`frontend/e2e/`) · the manual Browser E2E Preflight workflow · the checksum
verifier and manifests · the release documentation set.

## Protected quantitative outputs (regression fixtures — NOT performance promises)

These are frozen, verified fixture outputs used as regression tripwires:

- Scenario Studio severe cross-asset stress combo: composite severity
  **100.0/100**, **8 / 8** modules, "Severe systemic stress" regime.
- KO/PEP pairs fixture (pinned range 2016-07-11 → 2026-07-11): **119 trade
  events**, strategy Total Return **−23.0%** vs Buy & Hold **+112.7%**.

They describe deterministic educational sample data. They are not
performance claims, forecasts, or advice of any kind — the demo strategy
losing is intentional.

## Change policy (binding for future phases)

- New work happens in a new phase (and branch when appropriate) on top of
  this baseline; frozen tags are never moved or reused.
- Intentional behavior changes update the affected tests **and**
  `FROZEN_DEMO_REGRESSION_GUARD.md` in the same change — assertions are
  never loosened just to get green, and fixture outputs never change
  silently.
- Bug fixes are distinguished from model changes explicitly in the phase
  record.
- Frozen evidence is never overwritten; a future release mints a new
  evidence set (new screenshots, new manifests, new record docs).
- Frontend changes run the full sequence: typecheck → tests → local E2E →
  user-run build; releases additionally run both CI workflows on the release
  commit.
- New public evidence (runs, URLs, artifacts) is recorded in new evidence
  commits — never backfilled into frozen records.

## Post-release development lanes

1. **Product/UX** — new views, navigation, polish (respecting protected
   geometry).
2. **Quant research modules** — new labs on the established deterministic
   package pattern.
3. **Data provenance** — provenance labeling for the optional fail-closed
   adapters.
4. **Testing/CI** — harness growth, stability record, CI promotion
   decisions.
5. **Documentation** — onboarding, navigation, honest-labeling upkeep.
6. **Deployment exploration** — read-only hosted demo research; still
   non-production, still no claim until real.
7. **Public portfolio/demo content** — video, posts, case-study upkeep, all
   with recorded evidence.

## Next-phase candidates (listed, deliberately not selected)

- Promote Browser E2E to an opt-in PR gate once a stability record exists
  (criteria already in `CI_BROWSER_E2E.md` §12).
- Model validation & provenance dashboard.
- AFML meta-labeling lab.
- Purged cross-validation / CPCV lab.
- Data-quality & dataset lineage lab.
- Research experiment registry (building on the Phase 11/12 catalog work).
- Demo video production + publication evidence.
- Issue templates and contributor governance.

## Ground rules (unchanged by this doc)

Educational platform on deterministic sample data — not investment advice,
not production trading, risk, or compliance infrastructure; E2E/CI green is
a regression signal on a specific commit.
