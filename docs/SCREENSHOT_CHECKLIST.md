# QuantLab — Screenshot Checklist (Phase 38.0)

Capture targets for the newer labs and product layers. This extends
[`SCREENSHOT_PLAN.md`](SCREENSHOT_PLAN.md) (which covers the core backtest
views); the same rules apply:

> **Honesty rule:** every chart/metric must come from a real local run of the
> app — no fabricated data, no mocked screenshots. Dark theme, ~1440×900,
> PNG into `docs/screenshots/`. Avoid: loading spinners, error toasts,
> personal file paths, and raw JSON. Manual captures only — no automation
> required.

Every capture should keep the **"Static sample data" / "Static demo
metadata" hero badge visible** — the honest labeling is part of the pitch.

| # | View (sidebar route) | Set up before capture | Must be visible | Avoid | Suggested caption |
|---|---|---|---|---|---|
| 1 | Home dashboard (`home`) | Backend online; ≥2 saved backtests | Suggested Starting Paths strip, Quick Actions, API **ONLINE** | stale counts | "One shell for ~40 deterministic research workspaces." |
| 2 | Demo Center (`democenter`) | Select the Founder/Investor tour, audience "Investor" | Path selector, step cards with Open module buttons, module health cards | — | "Guided walkthroughs with hand-maintained module health." |
| 3 | Scenario Studio (`scenariostudio`) | Select Severe Cross-Asset Stress Combo | All-red heatmap, module impact chart, regime pill "Severe systemic stress" | — | "One scenario mapped into every module's documented impact score." |
| 4 | Research Workspace (`researchworkspace`) | Macro Stress pack, Summary view | Severity chart, workflow timeline, methodology checklist | empty note field close-ups | "An experiment journal with reproducibility checks." |
| 5 | Data Reliability Center (`datareliability`) | Full scope | Reliability gauge, provider table with yfinance marked "never" in tests | — | "Every module's data mode, fixtures, and provider caveats — documented." |
| 6 | QA Command Center (`qacommandcenter`) | Full scope | Release score gauge with its "not proof tests were run" caption, smoke matrix | — | "Release readiness as a product surface — verification stays local." |
| 7 | Portfolio Risk Lab (`risklab`) | Default sample portfolio | Metric cards + stress panel + formula panel | — | "Portfolio risk reads with the formulas beside the numbers." |
| 8 | Macro Regime Lab (`macroregime`) | Switch to Stagflation | Category score cards, regime pill, allocation comparison | — | "Hand-placed macro states, six distinct regimes." |
| 9 | Crypto Derivatives Lab (`cryptoderivatives`) | Drag funding shock ≠ 0 | Basis curve, funding P&L chart, liquidation distance chart, "educational estimate" label | — | "Perp funding & basis mechanics with deterministic shock sliders." |
| 10 | DeFi Risk Lab (`defirisk`) | Push utilization past the kink | Kinked rate curve, health-factor stress chart | — | "Kinked rate model + health-factor stress, all finite by construction." |
| 11 | Tokenomics Lab (`tokenomics`) | Unlock ×2, 180d horizon | Unlock bar+line chart, runway chart | — | "Unlock schedules, treasury runway, holder concentration." |
| 12 | On-Chain Analytics Lab (`onchain`) | Inflow ×3 | Flow bars flipped positive, NVT/velocity charts | — | "Exchange flows, cohorts, and whale reads on labeled sample data." |
| 13 | Alternative Data Lab (`altdata`) | Show the leakage scenario | Event timeline, decay curve, leakage guard flags | — | "Signal decay and leakage guards — with designed failure modes." |
| 14 | Options Lab (`options`) | Price one option; open payoff builder | Greeks, payoff chart, formula panel | — | "Black-Scholes to Heston, computed locally." |
| 15 | Volatility Surface Lab (`volatility`) | Default sample chain | Smile/term tables, variance-swap panel with its "not VIX methodology" note | — | "A volatility surface teaching lab that says what it isn't." |
| 16 | Market Microstructure Lab (`microstructure`) | BTCUSDT instrument; open TCA | Book summary, TCA attribution, toxicity metrics | — | "Order-book, TCA, and toxicity analytics on static sample tapes." |

Optional extras: Portfolio Showcase (`portfolioshowcase`) with the pitch
cards, and a command-palette shot (Ctrl/Cmd+K over any lab).

After capturing, update the status column thinking in
[`SCREENSHOT_PLAN.md`](SCREENSHOT_PLAN.md) and reference the images from the
README or portfolio page as needed.

## Release-evidence captures (Phase 42.2)

The release-gate verification (see
[`BROWSER_SMOKE_TEST_REPORT.md`](BROWSER_SMOKE_TEST_REPORT.md)) confirmed
these states render correctly in **production mode** (`npm run build` +
`next start`), but the in-session browser tooling **cannot export image
files** — and no browser-testing dependency is added just for screenshots.
So these five captures are **manual** (same rules as above; PNG into
`docs/screenshots/`):

| # | Capture | Exact setup | File name suggestion |
|---|---|---|---|
| R1 | Landing at 1440 px | Fresh load of `/`, API **ONLINE**, hero + Global Markets strip visible | `release_landing_1440.png` |
| R2 | Scenario Studio data-rich | Select "Severe Cross-Asset Stress Combo" → severity 100.0, all-red heatmap | `release_scenario_studio.png` |
| R3 | Home at 1024 px | Devtools width 1024; scroll to the Feature Map (badges must sit inside their cards) | `release_home_1024.png` |
| R4 | Home at 768 px | Devtools width 768; header wraps (controls under title), market chips show full % values | `release_home_768.png` |
| R5 | Pairs backtest result | Backtest → Pairs Trading (KO/PEP defaults) → Run; 119 trades, 4 charts, performance summary incl. the honest −23.0% vs B&H | `release_pairs_backtest.png` |

R3/R4 double as the regression record for the Phase 42.1 responsive fixes —
if a badge escapes its card or a chip clips its value, the fix regressed.
