\# STOP POINT - QuantLab



Date: 2026-06-26



\## Project Goal

QuantLab is a long-term multi-market AI quant research platform.



The current direction is:

\- futures-first

\- preserve existing crypto QuantLab code

\- upgrade in-place

\- do not start a parallel repo



\## Current Phase

Phase 1: futures-first foundation.



\## Current Known Completed Work

\- ES futures instrument spec layer added.

\- Relevant files include:

&#x20; - backend/app/instruments/\*

&#x20; - configs/instruments/es.yaml

&#x20; - backend/tests/test\_instruments\_registry.py

\- Previous test result:

&#x20; - 13 tests passed.



\## Important Rule

Do not implement these yet:

\- ML

\- CFDs

\- options

\- futures\_continuous

\- major backtest engine rewrite



Proceed one tiny commit at a time.



\## Next Safe Step

Review current repository state and make sure the futures instrument registry layer is clean, documented, and tested.



\## Risks

\- Jumping too quickly into ML before data/instrument layer is stable.

\- Rewriting existing crypto code instead of preserving and integrating it.

\- Making the platform too broad too early.

