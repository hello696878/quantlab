"""
Deterministic static-sample tokens for the Tokenomics Risk Lab (Phase 28.0).

Five illustrative tokens (L1, DeFi governance, gaming unlock, stablecoin
governance, low-float/high-FDV), each with a price/supply snapshot, an unlock
schedule (deterministic day offsets — no live clock), treasury balances, and a
holder-concentration snapshot. Identical every run and every test. Not live token
prices, not live on-chain data, no wallets / RPC / smart-contract calls, not
advice.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.tokenomics.models import (
    HolderConcentrationInput,
    TokenMarketInput,
    TokenomicsAnalysisRequest,
    TokenomicsSampleResponse,
    UnlockEventInput,
)

DISCLAIMER = (
    "Static illustrative sample data. Tokenomics, unlock, treasury, and "
    "concentration analytics are educational and not investment, trading, token, "
    "venture, legal, tax, or risk-management advice."
)


def _build(
    symbol: str,
    name: str,
    price: float,
    circ: float,
    total: float,
    max_supply: Optional[float],
    treasury_tokens: float,
    treasury_stables: float,
    burn: float,
    staking: float,
    emission: float,
    revenue: Optional[float],
    holders: Tuple[float, float, float, float, float, float],
    unlocks: List[Tuple[str, float, str, float, str]],  # (date, days, category, tokens, desc)
) -> TokenomicsAnalysisRequest:
    top1, top5, top10, insider, foundation, community = holders
    return TokenomicsAnalysisRequest(
        market=TokenMarketInput(
            symbol=symbol,
            token_name=name,
            price=price,
            circulating_supply=circ,
            total_supply=total,
            max_supply=max_supply,
            treasury_tokens=treasury_tokens,
            treasury_stables=treasury_stables,
            monthly_burn_usd=burn,
            staking_yield=staking,
            emission_rate_annual=emission,
            protocol_revenue_annual=revenue,
        ),
        unlock_events=[
            UnlockEventInput(date=d, days_until=days, category=cat, tokens=tok, description=desc)
            for (d, days, cat, tok, desc) in unlocks
        ],
        holder_concentration=HolderConcentrationInput(
            top_1_holder_share=top1,
            top_5_holder_share=top5,
            top_10_holder_share=top10,
            insider_share=insider,
            foundation_share=foundation,
            community_share=community,
        ),
    )


def sample_requests() -> List[TokenomicsAnalysisRequest]:
    return [
        # L1 token — high float, low emissions, deep treasury → balanced.
        _build(
            "L1_SAMPLE", "L1 Token Sample", 40.0, 550_000_000.0, 720_000_000.0, 720_000_000.0,
            30_000_000.0, 200_000_000.0, 8_000_000.0, 0.05, 0.04, 150_000_000.0,
            (0.06, 0.20, 0.33, 0.12, 0.10, 0.78),
            [
                ("T+30d", 30.0, "Validator rewards", 5_000_000.0, "Scheduled validator emission tranche."),
                ("T+120d", 120.0, "Ecosystem", 8_000_000.0, "Ecosystem grants tranche."),
                ("T+270d", 270.0, "Foundation", 10_000_000.0, "Foundation vesting tranche."),
                ("T+365d", 365.0, "Team", 12_000_000.0, "Team vesting cliff."),
            ],
        ),
        # DeFi governance token — rich emissions overwhelm staking → emission pressure.
        _build(
            "DEFI_GOV_SAMPLE", "DeFi Governance Token Sample", 6.5, 420_000_000.0, 600_000_000.0, 600_000_000.0,
            25_000_000.0, 40_000_000.0, 2_500_000.0, 0.06, 0.14, 30_000_000.0,
            (0.08, 0.24, 0.38, 0.18, 0.12, 0.70),
            [
                ("T+60d", 60.0, "Investor", 10_000_000.0, "Series A vesting tranche."),
                ("T+180d", 180.0, "Team", 12_000_000.0, "Team vesting tranche."),
                ("T+300d", 300.0, "Ecosystem", 15_000_000.0, "Liquidity-mining reserve tranche."),
            ],
        ),
        # Gaming token — heavy near-term unlock calendar → unlock pressure.
        _build(
            "GAMING_UNLOCK_SAMPLE", "Gaming Token Unlock Sample", 0.85, 900_000_000.0, 3_000_000_000.0, 3_000_000_000.0,
            100_000_000.0, 30_000_000.0, 4_000_000.0, 0.10, 0.06, 18_000_000.0,
            (0.09, 0.28, 0.45, 0.25, 0.15, 0.60),
            [
                ("T+30d", 30.0, "Play rewards", 60_000_000.0, "Play-to-earn rewards tranche."),
                ("T+90d", 90.0, "Investor", 90_000_000.0, "Private round cliff."),
                ("T+150d", 150.0, "Team", 60_000_000.0, "Team vesting tranche."),
                ("T+365d", 365.0, "Ecosystem", 150_000_000.0, "Ecosystem fund tranche."),
            ],
        ),
        # Stablecoin governance token — thin treasury vs burn → treasury runway risk.
        _build(
            "STABLE_GOV_SAMPLE", "Stablecoin Governance Token Sample", 1.8, 260_000_000.0, 300_000_000.0, 300_000_000.0,
            5_000_000.0, 6_000_000.0, 1_800_000.0, 0.04, 0.03, 9_600_000.0,
            (0.07, 0.22, 0.36, 0.10, 0.14, 0.76),
            [
                ("T+90d", 90.0, "Foundation", 6_000_000.0, "Foundation operations tranche."),
                ("T+270d", 270.0, "Team", 8_000_000.0, "Team vesting tranche."),
            ],
        ),
        # Low float / high FDV — 10% float at a 10× FDV ratio → low_float_high_fdv.
        _build(
            "LFHV_SAMPLE", "Low Float High FDV Sample", 2.0, 100_000_000.0, 1_000_000_000.0, 1_000_000_000.0,
            120_000_000.0, 25_000_000.0, 3_000_000.0, 0.08, 0.18, 12_000_000.0,
            (0.18, 0.42, 0.58, 0.30, 0.20, 0.50),
            [
                ("T+30d", 30.0, "Team", 4_000_000.0, "Team vesting cliff."),
                ("T+90d", 90.0, "Investor", 5_000_000.0, "Seed round cliff."),
                ("T+180d", 180.0, "Ecosystem", 3_000_000.0, "Ecosystem grants tranche."),
                ("T+365d", 365.0, "Foundation", 40_000_000.0, "Foundation mega-tranche."),
            ],
        ),
    ]


def build_sample_response() -> TokenomicsSampleResponse:
    return TokenomicsSampleResponse(
        tokens=sample_requests(),
        disclaimer=DISCLAIMER,
        notes=[
            "Five illustrative tokens (L1, DeFi governance, gaming unlock, stablecoin "
            "governance, low-float/high-FDV) with price/supply snapshots, unlock "
            "schedules on deterministic day offsets, treasury balances, and holder-"
            "concentration snapshots.",
            "Select / edit a token in the lab to explore the analytics.",
            "Not live token prices or on-chain data, no wallets / RPC / smart-contract "
            "calls, and not investment, trading, token, or venture advice.",
        ],
    )
