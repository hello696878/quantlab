"""
Deterministic static-sample DeFi markets for the DeFi Risk Lab (Phase 27.0).

Five illustrative samples (USDC lending, USDT peg stress, DAI collateralized
debt, ETH collateral borrowing, WBTC collateral stress), each with a stablecoin
peg snapshot, an Aave-like lending market with a kinked interest-rate model, and
a collateralized position. Identical every run and every test. Not live protocol
data, not live crypto prices, no wallets / RPC / smart-contract calls, not advice.
"""

from __future__ import annotations

from typing import List

from app.defi_risk.models import (
    CollateralPositionInput,
    DeFiMarketInput,
    DeFiRiskAnalysisRequest,
    DeFiRiskSampleResponse,
    StablecoinInput,
)

DISCLAIMER = (
    "Static illustrative sample data. DeFi lending, stablecoin peg, and liquidation "
    "analytics are educational and not investment, trading, lending, borrowing, "
    "liquidation, legal, tax, or risk-management advice."
)


def _build(
    sample_id: str,
    stable_symbol: str,
    stable_price: float,
    reserve_quality: float,
    asset_symbol: str,
    supplied: float,
    borrowed: float,
    coll_asset: str,
    coll_amount: float,
    coll_price: float,
    debt_asset: str,
    debt_amount: float,
    debt_price: float,
    liq_threshold: float,
    coll_factor: float,
    supply_apy: float,
    borrow_apy: float,
) -> DeFiRiskAnalysisRequest:
    return DeFiRiskAnalysisRequest(
        sample_id=sample_id,
        stablecoin=StablecoinInput(
            symbol=stable_symbol,
            target_peg=1.0,
            market_price=stable_price,
            supply_weight=0.25,
            reserve_quality_score=reserve_quality,
        ),
        market=DeFiMarketInput(
            protocol_name="Static Aave-like Sample",
            chain="Ethereum Sample",
            asset_symbol=asset_symbol,
            total_supplied=supplied,
            total_borrowed=borrowed,
            liquidity=supplied - borrowed,
            base_rate=0.01,
            slope_1=0.04,
            slope_2=0.60,
            kink_utilization=0.80,
            reserve_factor=0.10,
            lending_apy=supply_apy,
            borrow_apy=borrow_apy,
        ),
        position=CollateralPositionInput(
            collateral_asset=coll_asset,
            collateral_amount=coll_amount,
            collateral_price=coll_price,
            debt_asset=debt_asset,
            debt_amount=debt_amount,
            debt_price=debt_price,
            liquidation_threshold=liq_threshold,
            collateral_factor=coll_factor,
            liquidation_penalty=0.05,
            borrow_apy=borrow_apy,
            supply_apy=supply_apy,
        ),
        fees_apy=0.002,
    )


def sample_requests() -> List[DeFiRiskAnalysisRequest]:
    return [
        # USDC lending — tight peg, moderate utilization, safe position → healthy.
        _build(
            "USDC_LENDING_SAMPLE", "USDC_SAMPLE", 0.9998, 0.95,
            "USDC", 100_000_000.0, 65_000_000.0,
            "ETH", 5.0, 3500.0, "USDC", 6000.0, 1.0,
            0.80, 0.75, 0.025, 0.055,
        ),
        # USDT peg stress — 150 bps discount to peg → peg stress.
        _build(
            "USDT_PEG_STRESS_SAMPLE", "USDT_SAMPLE", 0.985, 0.70,
            "USDT", 80_000_000.0, 56_000_000.0,
            "ETH", 6.0, 3500.0, "USDT", 9000.0, 0.985,
            0.80, 0.75, 0.030, 0.062,
        ),
        # DAI collateralized debt — utilization above the kink → elevated utilization.
        _build(
            "DAI_CDP_SAMPLE", "DAI_SAMPLE", 0.999, 0.85,
            "DAI", 60_000_000.0, 51_000_000.0,
            "WETH", 8.0, 3500.0, "DAI", 17000.0, 0.999,
            0.80, 0.75, 0.048, 0.085,
        ),
        # ETH collateral borrowing — the classic Aave-like example → healthy.
        _build(
            "ETH_COLLATERAL_SAMPLE", "USDC_SAMPLE", 0.9998, 0.95,
            "USDC", 100_000_000.0, 65_000_000.0,
            "ETH", 10.0, 3500.0, "USDC", 18000.0, 1.0,
            0.80, 0.75, 0.025, 0.055,
        ),
        # WBTC collateral stress — hot utilization + thin health factor → liquidation watch.
        _build(
            "WBTC_STRESS_SAMPLE", "USDC_SAMPLE", 0.9995, 0.95,
            "USDC", 50_000_000.0, 46_000_000.0,
            "WBTC", 0.5, 95000.0, "USDC", 33000.0, 1.0,
            0.78, 0.70, 0.041, 0.118,
        ),
    ]


def build_sample_response() -> DeFiRiskSampleResponse:
    return DeFiRiskSampleResponse(
        samples=sample_requests(),
        disclaimer=DISCLAIMER,
        notes=[
            "Five illustrative DeFi samples (USDC lending, USDT peg stress, DAI "
            "collateralized debt, ETH collateral borrowing, WBTC collateral stress) "
            "with stablecoin peg snapshots, Aave-like kinked rate-model markets, and "
            "collateralized positions.",
            "Select / edit a sample in the lab to explore the analytics.",
            "Not live protocol data or crypto prices, no wallets / RPC / smart-contract "
            "calls, and not investment, lending, borrowing, or liquidation advice.",
        ],
    )
