# 90-Second Demo Video Script (Phase 44.0)

Timestamped, word-for-word. Setup and retake rules:
[`DEMO_VIDEO_SHOT_LIST.md`](DEMO_VIDEO_SHOT_LIST.md). Speak ~150 wpm; if a
segment runs long, cut words, not claims-discipline.

## 0:00–0:10 — Hook *(on: Home, fresh load, API ONLINE visible)*

**Say:** "This is QuantLab — a local-first quant research platform I built:
about forty interactive research workspaces, every one running on
deterministic sample data."

**Click:** nothing; slow scroll to the Global Markets strip.

## 0:10–0:25 — Architecture *(on: Home, brief sidebar hover)*

**Say:** "FastAPI and Pydantic on the back, Next.js and TypeScript on the
front, SQLite for local saves. No accounts, no cloud, no live-data
dependency — the optional adapters are off by default and fail closed."

**Click:** hover the sidebar groups top to bottom once.

## 0:25–0:45 — Frozen demo path *(navigate while talking)*

**Say:** "The public demo path is frozen and evidence-backed. The Release
Candidate page tracks readiness honestly — every status is a recorded,
user-run check, and nothing claims a pass it didn't earn."

**Click:** sidebar → Portfolio Showcase (beat) → Public Release Candidate;
hover the RC status cards.

## 0:45–1:05 — Scenario Studio + KO/PEP *(the money shots)*

**Say:** "Scenario Studio maps one stress template through documented
weights into every module — severe combo drives severity to one hundred,
eight of eight modules. And the pairs backtest is a deterministic fixture:
same one hundred nineteen trades on any machine. It loses money — honest
numbers are the feature, not a bug."

**Click:** sidebar → Scenario Studio → click **Severe Cross-Asset Stress
Combo**, let the gauge hit 100.0 → sidebar → Backtest → Pairs Trading →
Run Backtest (pre-warmed in rehearsal so results land inside the beat).

## 1:05–1:20 — E2E regression guard *(on: terminal or HTML report)*

**Say:** "That exact demo path is protected by a twelve-test Playwright
guard — route walk, the scenario result, the pairs fixture, and responsive
geometry at three widths. If the frozen demo regresses, it fails loudly."

**Click:** show the `12 passed` output from a run you actually did today.

## 1:20–1:30 — Close *(back on: Home)*

**Say:** "It's educational by design — not a trading system, not advice.
The limitations doc ships with the repo, and it's the first thing I'd show
you. Link below."

**Click:** none. Hold Home for two beats; end.

## What NOT to say (any take)

No "production-ready" / "institutional-grade" / "audited" / "certified" ·
no investment or trading advice, no signals · no alpha or performance
promises · no live-data guarantees · no invented users/customers/revenue ·
don't call E2E/CI green a certification — it's a regression signal.

## Ground rules

Deterministic educational sample data; not investment advice; not
production trading, risk, or compliance infrastructure.
