# QuantLab — Frozen Demo Regression Guard (Phase 43.0)

What the E2E harness protects, what may not change casually, and how to
evolve the guard honestly. Runbook: [`BROWSER_E2E_RUNBOOK.md`](BROWSER_E2E_RUNBOOK.md).

## 1. The frozen baseline

| Record | Value |
|---|---|
| Frozen release tag | `v4.60.0-public-release-candidate-demo-freeze-v1` |
| Freeze evidence commit | `7cf9708` (five R1–R5 screenshots + freeze record) |
| Verified application commit | `c059c4e` |
| Frozen evidence files | `docs/screenshots/release_*.png` — never regenerated, never overwritten |

## 2. Protected workflows (encoded in `frontend/e2e/*.spec.ts`)

1. **Landing** — hero, dashboard, API ONLINE health chip.
2. **Public Release Candidate** page opens and reads correctly.
3. **Scenario Studio severe stress combo** — analyze POST 200 → severity
   **100.0/100**, **8 / 8** modules, "Severe systemic stress", heatmap +
   charts. (The pre-stress 11.3 baseline belongs to the Soft Landing
   template and is preserved in the manual freeze evidence.)
4. **KO/PEP Pairs Trading fixture** — pinned range 2016-07-11 → 2026-07-11 →
   **119 trades**, **−23.0%** vs **+112.7%** B&H, 4 charts, trade log, no
   live provider.
5. **Saved Reports** controlled empty state.
6. **Command palette** — Ctrl+K opens, search navigates.
7. **Responsive 1440/1024/768** — no overflow; the three fixed Phase 42.1
   defects (badges D1, TopBar D2, market chips D3) stay fixed.

## 3. What must NOT change without a deliberate post-freeze decision

- The deterministic KO/PEP fixture semantics (`app/data.py`) or its
  demo-pair short-circuit in the backend.
- Scenario Studio's template weights/thresholds that produce the 100.0
  severe-combo reading.
- The sidebar labels and page titles the demo script and these tests
  navigate by ("Scenario Studio", "Backtest", "Public Release Candidate", …).
- The frozen evidence files and the freeze record
  ([`DEMO_FREEZE_CHECKLIST.md`](DEMO_FREEZE_CHECKLIST.md) §1).
- The frozen tag itself — never force-updated, never re-pointed.

If one of these must change, that is a *new phase decision*: change it, update
the affected spec assertions in the same change, record the why in ROADMAP,
and treat the old numbers as historical (the freeze record keeps them).

## 4. What can change safely

New views, new labs, new docs, styling that keeps the protected geometry
sound, backend additions that don't alter the fixture outputs, copy edits
outside the navigated labels — the guard is deliberately narrow so normal
development stays free.

## 4b. Where the guard runs

Locally (primary — [`BROWSER_E2E_RUNBOOK.md`](BROWSER_E2E_RUNBOOK.md)), and
on demand in an isolated CI runner via the manually triggered
**Browser E2E Preflight** workflow ([`CI_BROWSER_E2E.md`](CI_BROWSER_E2E.md))
— `workflow_dispatch` only, non-blocking, evidence uploaded as temporary
workflow artifacts.

## 5. Updating the guard in future phases

- New protected workflow → new spec file under `frontend/e2e/`, listed here.
- Changed frozen expectation → update the assertion *and* this document in
  the same commit; never loosen an assertion just to get green.
- Keep v1's rules: no external network, no live providers, no visual
  snapshot baselines without a dedicated decision, artifacts only under
  `artifacts/e2e/`.

## 6. Evidence policy

Generated E2E output (traces, failure screenshots, HTML reports) lives under
`artifacts/e2e/` — gitignored, disposable, never committed. Durable release
evidence remains the five frozen `docs/screenshots/release_*.png` files plus
the freeze record; a future release candidate would mint a *new* evidence
set rather than touching the frozen one.

## Ground rules (unchanged by this doc)

E2E green is a regression signal, not a certification. Deterministic sample
data; no live trading; not investment advice; not production trading, risk,
or compliance infrastructure.
