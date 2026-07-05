"""
Deterministic static-sample networks for the On-Chain Analytics Lab (Phase 29.0).

Five illustrative networks/tokens (BTC-like, ETH-like, L1 exchange-reserve, DeFi
governance whale, exchange-inflow stress), each with an exchange-flow snapshot,
24h activity metrics, six holder cohorts, and a whale-flow snapshot. Identical
every run and every test. Not live on-chain data, not live token prices, no
wallets / RPC / smart-contract / explorer / exchange API calls, not advice.
"""

from __future__ import annotations

from typing import List, Tuple

from app.onchain_analytics.models import (
    HolderCohortInput,
    OnChainAnalysisRequest,
    OnChainNetworkInput,
    OnChainSampleResponse,
    WhaleFlowInput,
)

DISCLAIMER = (
    "Static illustrative sample data. On-chain flow, exchange reserve, whale "
    "concentration, and activity analytics are educational and not investment, "
    "trading, token, legal, tax, or risk-management advice."
)

_COHORT_DESCRIPTIONS = {
    "Retail wallets": "Small self-custody wallets.",
    "Mid-size wallets": "Mid-size self-custody wallets.",
    "Large holders": "Large non-whale holders.",
    "Whale wallets": "Very large individual holders.",
    "Treasury / foundation-like wallets": "Protocol treasury / foundation-style wallets.",
    "Exchange-labeled wallets": "Wallets labelled as exchange-controlled in this sample.",
}


def _cohorts(rows: List[Tuple[str, float, float]]) -> List[HolderCohortInput]:
    return [
        HolderCohortInput(
            cohort_name=name,
            holder_count=count,
            token_balance=balance,
            description=_COHORT_DESCRIPTIONS.get(name),
        )
        for (name, count, balance) in rows
    ]


def _build(
    symbol: str,
    token_name: str,
    network_name: str,
    price: float,
    circ: float,
    reserve: float,
    inflow: float,
    outflow: float,
    addresses: float,
    transfer_volume: float,
    tx_count: float,
    cohorts: List[Tuple[str, float, float]],
    whale_in: float,
    whale_out: float,
    top10: float,
    top50: float,
    top100: float,
) -> OnChainAnalysisRequest:
    return OnChainAnalysisRequest(
        network=OnChainNetworkInput(
            symbol=symbol,
            token_name=token_name,
            network_name=network_name,
            token_price=price,
            circulating_supply=circ,
            exchange_reserve_tokens=reserve,
            exchange_inflow_tokens_24h=inflow,
            exchange_outflow_tokens_24h=outflow,
            active_addresses_24h=addresses,
            transfer_volume_tokens_24h=transfer_volume,
            transaction_count_24h=tx_count,
        ),
        holder_cohorts=_cohorts(cohorts),
        whale_flow=WhaleFlowInput(
            whale_inflow_tokens_24h=whale_in,
            whale_outflow_tokens_24h=whale_out,
            top_10_holder_share=top10,
            top_50_holder_share=top50,
            top_100_holder_share=top100,
        ),
    )


def sample_requests() -> List[OnChainAnalysisRequest]:
    return [
        # BTC-like — balanced flows and moderate concentration → balanced activity.
        _build(
            "BTC_ONCHAIN_SAMPLE", "BTC On-Chain Sample", "Static Bitcoin-like Sample",
            65000.0, 19_800_000.0, 2_400_000.0, 30_000.0, 32_000.0,
            950_000.0, 450_000.0, 620_000.0,
            [
                ("Retail wallets", 45_000_000.0, 3_200_000.0),
                ("Mid-size wallets", 1_200_000.0, 4_000_000.0),
                ("Large holders", 90_000.0, 4_600_000.0),
                ("Whale wallets", 2_200.0, 3_400_000.0),
                ("Treasury / foundation-like wallets", 150.0, 1_200_000.0),
                ("Exchange-labeled wallets", 350.0, 3_400_000.0),
            ],
            9_000.0, 11_000.0, 0.06, 0.18, 0.26,
        ),
        # ETH-like — hot transfer velocity with healthy activity → high-velocity regime.
        _build(
            "ETH_ONCHAIN_SAMPLE", "ETH On-Chain Sample", "Static Ethereum-like Sample",
            3500.0, 120_000_000.0, 14_000_000.0, 250_000.0, 240_000.0,
            550_000.0, 22_000_000.0, 1_150_000.0,
            [
                ("Retail wallets", 60_000_000.0, 18_000_000.0),
                ("Mid-size wallets", 2_500_000.0, 26_000_000.0),
                ("Large holders", 180_000.0, 30_000_000.0),
                ("Whale wallets", 5_000.0, 22_000_000.0),
                ("Treasury / foundation-like wallets", 300.0, 10_000_000.0),
                ("Exchange-labeled wallets", 500.0, 14_000_000.0),
            ],
            120_000.0, 110_000.0, 0.08, 0.20, 0.28,
        ),
        # L1 token — sustained exchange outflows → outflow / accumulation regime.
        _build(
            "L1_RESERVE_SAMPLE", "L1 Token Exchange Reserve Sample", "Static L1 Sample",
            12.0, 800_000_000.0, 90_000_000.0, 4_000_000.0, 16_000_000.0,
            140_000.0, 30_000_000.0, 260_000.0,
            [
                ("Retail wallets", 2_400_000.0, 160_000_000.0),
                ("Mid-size wallets", 300_000.0, 180_000_000.0),
                ("Large holders", 40_000.0, 170_000_000.0),
                ("Whale wallets", 900.0, 130_000_000.0),
                ("Treasury / foundation-like wallets", 40.0, 70_000_000.0),
                ("Exchange-labeled wallets", 120.0, 90_000_000.0),
            ],
            2_000_000.0, 5_000_000.0, 0.15, 0.28, 0.38,
        ),
        # DeFi governance token — top holders dominate → whale concentration risk.
        _build(
            "DEFI_WHALE_SAMPLE", "DeFi Governance Whale Sample", "Static Ethereum-like Sample",
            22.0, 150_000_000.0, 20_000_000.0, 1_500_000.0, 1_200_000.0,
            60_000.0, 6_000_000.0, 95_000.0,
            [
                ("Retail wallets", 450_000.0, 18_000_000.0),
                ("Mid-size wallets", 60_000.0, 24_000_000.0),
                ("Large holders", 9_000.0, 30_000_000.0),
                ("Whale wallets", 400.0, 45_000_000.0),
                ("Treasury / foundation-like wallets", 25.0, 18_000_000.0),
                ("Exchange-labeled wallets", 60.0, 15_000_000.0),
            ],
            800_000.0, 700_000.0, 0.34, 0.52, 0.63,
        ),
        # Exchange inflow stress — heavy 24h deposits → inflow-pressure regime.
        _build(
            "FLOW_SAMPLE", "Exchange Inflow Stress Sample", "Static Ethereum-like Sample",
            4.5, 500_000_000.0, 120_000_000.0, 18_000_000.0, 9_000_000.0,
            85_000.0, 65_000_000.0, 210_000.0,
            [
                ("Retail wallets", 1_600_000.0, 90_000_000.0),
                ("Mid-size wallets", 240_000.0, 110_000_000.0),
                ("Large holders", 30_000.0, 105_000_000.0),
                ("Whale wallets", 700.0, 80_000_000.0),
                ("Treasury / foundation-like wallets", 30.0, 45_000_000.0),
                ("Exchange-labeled wallets", 90.0, 70_000_000.0),
            ],
            9_000_000.0, 3_000_000.0, 0.22, 0.43, 0.57,
        ),
    ]


def build_sample_response() -> OnChainSampleResponse:
    return OnChainSampleResponse(
        networks=sample_requests(),
        disclaimer=DISCLAIMER,
        notes=[
            "Five illustrative networks/tokens (BTC-like, ETH-like, L1 exchange "
            "reserve, DeFi governance whale, exchange-inflow stress) with exchange-"
            "flow snapshots, 24h activity metrics, six holder cohorts, and whale-"
            "flow snapshots.",
            "Select / edit a sample in the lab to explore the analytics.",
            "Not live on-chain data, token prices, wallets, RPC, smart-contract, "
            "explorer, or exchange APIs — and not investment, trading, or token advice.",
        ],
    )
