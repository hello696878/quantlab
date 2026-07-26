"""
Transaction Cost, Slippage, Market Impact and Capacity Diagnostics Lab (v1).

Local-first research diagnostics that apply explicitly configured execution-cost
assumptions to supplied historical trade-level or period-level observations:
unit-safe cost normalization, commission / spread / slippage / market-impact
components, no-look-ahead liquidity inputs, gross-to-net reconciliation,
break-even diagnostics, a bounded cost-sensitivity grid, and notional-scaling
capacity diagnostics with participation warnings.

The lab is NOT an order execution system, broker simulator, or live trading
engine.  It does not predict real fills, guarantee market capacity, recommend
trade sizes or brokers, prove profitability, or provide investment or
execution advice.  All outputs are estimates under configured assumptions.
"""

EXPORT_SCHEMA_VERSION = "cost_diagnostics_export_v1"
