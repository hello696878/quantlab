"""
Deterministic static-sample inputs for the Real Estate Lab (Phase 22.0).

An illustrative urban apartment with a sample mortgage and a sample REIT. All
values are hand-authored and fixed — identical every run and every test. Not
live data, not advice.
"""

from __future__ import annotations

from app.real_estate.models import (
    DebtInput,
    PropertyInput,
    RealEstateAnalysisRequest,
    ReitInput,
    SampleResponse,
)

DISCLAIMER = (
    "Static illustrative sample data. Real-estate analytics are educational and "
    "not investment, tax, legal, or lending advice."
)


def sample_property() -> PropertyInput:
    return PropertyInput(
        property_name="Urban Apartment Sample",
        property_type="Multifamily",
        market="Sample Metro",
        purchase_price=10_000_000.0,
        gross_rent_annual=720_000.0,
        other_income_annual=30_000.0,
        vacancy_rate=0.05,
        operating_expenses_annual=280_000.0,
        capex_reserve_annual=40_000.0,
        purchase_costs=200_000.0,
        exit_cap_rate=0.055,
        holding_period_years=5,
    )


def sample_debt() -> DebtInput:
    return DebtInput(
        loan_amount=6_500_000.0,
        interest_rate=0.055,
        amortization_years=30,
        term_years=5,
        interest_only_years=0,
        points_or_fees=0.0,
    )


def sample_reit() -> ReitInput:
    return ReitInput(
        property_nav=1_200_000_000.0,
        net_debt=450_000_000.0,
        shares_outstanding=30_000_000.0,
        share_price=22.0,
        funds_from_operations=85_000_000.0,
        dividend_per_share=1.2,
    )


def sample_request() -> RealEstateAnalysisRequest:
    return RealEstateAnalysisRequest(
        property=sample_property(),
        debt=sample_debt(),
        reit=sample_reit(),
        selling_cost_rate=0.02,
    )


def build_sample_response() -> SampleResponse:
    return SampleResponse(
        request=sample_request(),
        disclaimer=DISCLAIMER,
        notes=[
            "Illustrative urban apartment, sample mortgage, and sample REIT — "
            "static hand-authored values.",
            "Edit the assumptions in the lab to explore the analytics.",
            "Not live property or REIT data, and not investment advice.",
        ],
    )
