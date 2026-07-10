# QuantLab — Interview Talking Points (Phase 38.0)

Prepared answers from two angles — software engineering and quant research.
Everything here is factual about the repo; no exaggerated claims.

---

## 1. Architecture (the 90-second version)

Monorepo, two services. The backend is FastAPI with one repeated pattern:
each lab is a package of `models.py` (strict Pydantic v2 — `extra="forbid"`,
finite-float types so NaN/Infinity can't cross the API), `sample.py`
(hand-written deterministic sample data), and `service.py` (pure functions,
no I/O), exposed as `GET /<lab>/sample` + `POST /<lab>/analyze`. The frontend
is a Next.js 14 single-page shell: a view union type, grouped sidebar,
command palette, and per-lab panels that pair a typed API client with
debounced auto-analyze. Persistence is local SQLite for saved work;
everything else is stateless. Docker Compose for packaging; GitHub Actions
runs backend tests and a frontend build.

## 2. Backend design decisions

- **Why one contract for every lab?** Sixteen lab routers share the
  sample/analyze shape, so every new lab inherits testing patterns, error
  handling, and frontend wiring — the marginal cost of a lab dropped phase
  over phase.
- **Why pure service functions?** Analytics take a validated request and
  return a validated response — no globals, no clocks, no network — which is
  what makes ~2,900 tests deterministic and fast.
- **Validation philosophy:** reject at the boundary (422 with readable
  detail), guarantee finiteness by construction inside (guarded divisions,
  clipped scores), and test the guarantee (`_assert_all_finite` walks every
  response).

## 3. Frontend design decisions

- Single-page shell over per-route pages: one navigation model (sidebar +
  palette + dashboard) and instant view switching; app-router
  error/loading/not-found files plus a root error boundary provide safety.
- Shared primitives over per-lab code: one chart library wrapper
  (non-finite filtering, empty states, theme tokens, aria labels), one
  formula system (local KaTeX with a crash-proof fallback), one slider, one
  set of state components (loading/empty/error/offline).
- Design tokens (CSS variables) instead of raw colors — the whole app
  re-skins from one accent setting, and dark-mode readability is enforced in
  one place.

## 4. Data reliability story

The platform's one real external dependency is yfinance for user-configured
backtests. Three mitigations, all documented in-app (Data Reliability
Center): the built-in KO/PEP pairs demo falls back to a deterministic
network-free fixture; backend API tests monkeypatch the fetch layer; and the
globe's optional FRED/delayed-quote adapters are disabled by default and
fail closed to static data. Policy: tests never depend on a live provider,
default demos are deterministic, and external availability is never claimed.

## 5. Testing strategy

Deterministic-by-construction: every lab's tests hit the real FastAPI app via
TestClient with the real sample data — no network, no mocking except the
explicit yfinance fetch layer. Each phase added its own suite (endpoints,
formula spot-checks against hand-computed values, validation rejections,
JSON-safety walks, and wording contracts — e.g. reports must not contain
recommendation language or claim tests were run). Frontend: strict
TypeScript with `tsc --noEmit`; no frontend test framework yet — that's a
known gap I'd close next.

## 6. UX / product decisions

The differentiator is the product layer on top of the labs: Demo Center
(audience-specific guided tours), Scenario Studio (cross-lab stress with
report export), Research Workspace (experiment journal + reproducibility
checklist), Data Reliability + QA Command Centers (the quality story as a
product surface). Guiding principle: **the platform explains itself** —
data-mode badges, limitation notes, and formulas live in the UI, not just in
docs.

## 7. Quant modeling choices

Educational versions of standard models, chosen to teach mechanics:
Black-Scholes through Heston MC, CRR trees, vol surfaces + a variance-swap
strip (explicitly *not* the VIX methodology), Vasicek/CIR, Merton +
reduced-form credit, CPR/SMM/PSA prepayment, cost-of-carry, microstructure
(microprice, implementation shortfall, TCA that sums to shortfall by
construction, VPIN-style toxicity), AFML methodology (triple-barrier, purged
CV + embargo, sequential bootstrap, fracdiff), and the crypto suite (funding/
basis, kinked rate-model health factors, unlock schedules, flow analytics).
Deliberate simplifications are documented per model — e.g. the liquidation
price is a closed-form classroom estimate, not an exchange engine.

## 8. Limitations (say them before being asked)

- All analytics are educational simplifications on hand-written sample data —
  nothing is calibrated, nothing is evidence of alpha.
- The in-app health/reliability/QA scores are documentation-coverage reads
  over hand-maintained registries — not telemetry, not CI, not proof
  anything ran.
- No frontend test framework; accessibility polish is targeted, not audited.
- Single-user, local-first by design: no auth, no multi-user story, no
  hosted deployment yet.

## 9. What I'd improve next

1. Frontend testing (component tests for the shared primitives first).
2. Registry drift tests — cross-check hand-maintained metadata against the
   actual route table so stale flags fail CI (one such drift was caught and
   fixed manually in Phase 36).
3. Deep links with pre-filled state (e.g. "open Scenario Studio with the
   severe combo selected") building on the existing initial-tab pattern.
4. A hosted read-only demo once the deployment-readiness gaps are closed.
5. Real historical data adapters behind the same fail-closed pattern, for
   labs where it's safe and clearly labeled.

## 10. Likely Q&A

- **"Why not real market data?"** — Determinism. Reproducible demos and
  offline tests were worth more than realism for an educational platform;
  the adapter pattern (opt-in, fail-closed) leaves the door open.
- **"How do you know the models are right?"** — Formula spot-check tests
  against hand-computed values, plus documented simplifications. "Right"
  here means "matches the stated teaching formula," not "matches the market."
- **"What was the hardest part?"** — Keeping 38 phases consistent: the
  shared contracts (API shape, panel skeleton, docs-per-phase) are what kept
  a large solo codebase coherent.
- **"Is this used in production?"** — No, and it doesn't claim to be. It's
  an educational and portfolio project; the honest labeling is deliberate.
- **"What would it take to make it production-grade?"** — Real data
  contracts, calibration and validation against market data, authn/z,
  monitoring, and a compliance review — none of which exist today, which the
  limitations ledger states plainly.
- **"Biggest engineering lesson?"** — Guarantees at the boundary (strict
  schemas, finiteness, wording contracts *as tests*) scale better than
  vigilance in the middle.
