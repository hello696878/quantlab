"""Retrospective purged validation of fixed scanner selections; no supervised fit."""
from datetime import date
from typing import Any, Literal

import numpy as np
from pydantic import Field, StrictInt, model_validator

from app.model_validation.engine import audit_split, purged_kfold, validate_config
from app.model_validation.events import normalize_samples, strip_datetimes
from app.model_validation.fingerprints import configuration_fingerprint, split_fingerprint
from app.overfitting_diagnostics.multiple_testing import adjust_p_values
from app.run_replay.identity import digest
from app.scanner.advanced import advanced_weights, keyed_panel
from app.scanner.cross_sectional import validate_scanner_inputs
from app.scanner.policies import AssetId, Declaration, Finite, NeutralisationPolicy
from app.scanner.sample_data import generate_sample_universe
from app.scanner.signals import momentum_score, reversal_score
from app.scanner.pnl import portfolio_pnl
from app.schemas import ScannerRequest


class ScannerCandidate(Declaration):
    candidate_id: AssetId
    strategy: Literal["cross_sectional_reversal", "cross_sectional_momentum"]
    policy: NeutralisationPolicy = Field(default_factory=NeutralisationPolicy)
    raw_p_value: Finite | None = Field(default=None, ge=0, le=1)
    p_value_source: str = Field(default="caller declaration, not computed by this scanner", min_length=1, max_length=200)
    hypothesis: str = Field(default="caller-declared null; no supported inferential test executed", min_length=1, max_length=300)
    p_value_scope: Literal["declared_external", "this_scanner_sample"] = "declared_external"


class ScannerValidationRequest(Declaration):
    scanner: ScannerRequest
    candidates: list[ScannerCandidate] = Field(min_length=1, max_length=4)
    n_folds: StrictInt = Field(default=3, ge=2, le=5)
    embargo_days: Finite = Field(default=1.0, ge=0, le=30)
    alpha: Finite = Field(default=0.05, ge=0.001, le=0.5)

    @model_validator(mode="after")
    def family(self):
        ids = [c.candidate_id for c in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate IDs must be unique in the entire declared family")
        if self.scanner.n_assets > 30 or (date.fromisoformat(self.scanner.end_date) - date.fromisoformat(self.scanner.start_date)).days > 420:
            raise ValueError("validation is bounded to 30 assets and 420 calendar days")
        return self


class CandidateResult(Declaration):
    candidate_id: str
    status: Literal["available", "unavailable"]
    reason: str | None
    mean_test_net_return: float | None
    outcomes: list[dict[str, Any]]
    correction: dict[str, Any]


class ScannerValidationResponse(Declaration):
    schema_version: Literal["scanner_validation_v1"] = "scanner_validation_v1"
    input_fingerprint: str
    family_fingerprint: str
    result_fingerprint: str
    split_configuration_fingerprint: str
    samples: list[dict[str, Any]]
    folds: list[dict[str, Any]]
    candidates: list[CandidateResult]
    family: dict[str, Any]
    material: dict[str, Any]
    caveats: list[str]
    unavailable_statistics: dict[str, str]
    conventions: dict[str, Any]


def verify_validation_bundle(bundle):
    """Integrity of retained material, not a certificate of valid statistical claims."""
    body = dict(bundle)
    expected = body.pop("result_fingerprint")
    if digest(body) != expected or digest(body["material"]["panel"]) != body["input_fingerprint"]:
        raise ValueError("retained scanner material/result fingerprint mismatch")
    return True


def run_scanner_validation(request, *, universe=None):
    request = ScannerValidationRequest.model_validate(request)
    spec = request.scanner
    validate_scanner_inputs(spec.strategy, spec.n_assets, spec.start_date, spec.end_date, spec.lookback_days,
                            spec.long_quantile, spec.short_quantile, spec.rebalance_frequency,
                            spec.gross_exposure, spec.cost_bps, spec.min_liquidity, spec.seed)
    uni = universe if universe is not None else generate_sample_universe(spec.n_assets, spec.start_date, spec.end_date, spec.seed if spec.seed is not None else 42)
    dates = uni["dates"]
    if len(dates) > 300 or spec.lookback_days >= len(dates) - 4:
        raise ValueError("validation requires at most 300 dates and at least four actionable samples")
    scorer = reversal_score if spec.strategy == "cross_sectional_reversal" else momentum_score
    panel = keyed_panel(uni, scorer(uni["prices"], spec.lookback_days), spec.advanced_inputs)
    decision_indices = list(range(spec.lookback_days, len(dates) - 1))
    raw_samples = [{"sample_id": f"cs:{panel['fingerprint'][:16]}:{dates[t]}",
                    "prediction_time": dates[t] + "T00:00:00+00:00",
                    "evaluation_time": dates[t + 1] + "T00:00:00+00:00",
                    "group": dates[t], "metadata": {"decision_index": t, "feature_start": dates[t - spec.lookback_days],
                        "feature_end": dates[t], "unit": "one entire contemporaneous cross-section", "input_fingerprint": panel["fingerprint"]}}
                   for t in decision_indices]
    samples = normalize_samples(raw_samples)
    config = {"n_folds": request.n_folds, "embargo": {"mode": "duration_days", "value": request.embargo_days}}
    validate_config("purged_kfold", samples, config)
    splits = purged_kfold(samples, config)
    config_fp = configuration_fingerprint(method="purged_kfold", samples=samples, configuration=config)
    folds = []
    for split in splits:
        memberships = {name.removesuffix("_pos") + "_ids": [samples[p]["sample_id"] for p in split[name]]
                       for name in ("train_pos", "test_pos", "purged_pos", "embargoed_pos")}
        audit = audit_split(samples, split, "purged_kfold")
        folds.append({"label": split["split_label"], **memberships, "audit": audit,
                      "fingerprint": split_fingerprint(configuration_fp=config_fp, split_label=split["split_label"], **memberships),
                      "trained_parameters": [], "training_used_for_fit": False})
    candidate_declarations = [c.model_dump(mode="json") for c in request.candidates]
    family_fp = digest({"schema_version": "scanner_family_v1", "input": panel["fingerprint"], "candidates": candidate_declarations,
                        "split_configuration": config, "cost_bps": spec.cost_bps, "alpha": request.alpha})
    entries = [{"candidate_id": c.candidate_id, "raw_p": c.raw_p_value,
                "provenance": {"source": c.p_value_source, "hypothesis": c.hypothesis,
                               "scope": c.p_value_scope, "input_fingerprint": panel["fingerprint"],
                               "family_fingerprint": family_fp}} for c in request.candidates]
    corrections = adjust_p_values(entries, request.alpha)
    results = []
    for candidate, correction in zip(request.candidates, corrections):
        reason = None
        if spec.rebalance_frequency != "daily":
            reason = "v1 held-out adapter supports daily decisions only; weekly/monthly carried holdings are unavailable"
        elif candidate.policy.mode == "beta" or candidate.policy.volatility is not None:
            reason = "beta/volatility policies require a fold-specific frozen estimation or supplied-exposure validation contract; not supported by this adapter"
        elif not all(f["audit"]["valid"] for f in folds):
            reason = "at least one split has an invalid or empty retained training/test set"
        outcomes = []
        if reason is None:
            scorer = reversal_score if candidate.strategy == "cross_sectional_reversal" else momentum_score
            actual = keyed_panel(uni, scorer(uni["prices"], spec.lookback_days), spec.advanced_inputs)
            # No supervised or full-sample learned policy: transformation uses only this decision's scores/declarations.
            selected = advanced_weights(actual, set(decision_indices), candidate.policy,
                long_quantile=spec.long_quantile, short_quantile=spec.short_quantile,
                gross=spec.gross_exposure, min_liquidity=spec.min_liquidity)
            for split, fold in zip(splits, folds):
                weights = np.zeros_like(selected["weights"])
                indices = [samples[p]["metadata"]["decision_index"] for p in split["test_pos"]]
                weights[indices] = selected["weights"][indices]
                pnl = portfolio_pnl(weights, uni["returns"], spec.cost_bps)
                for p, t in zip(split["test_pos"], indices):
                    outcomes.append({"sample_id": samples[p]["sample_id"], "fold": fold["label"],
                                     "decision_date": dates[t], "outcome_date": dates[t + 1],
                                     "gross_return": float(pnl["gross"][t + 1]), "net_return": float(pnl["net"][t + 1]),
                                     "turnover": float(pnl["turnover"][t]), "cost": float(pnl["cost"][t]),
                                     "weights": dict(zip(uni["tickers"], map(float, weights[t])))})
        results.append({"candidate_id": candidate.candidate_id, "status": "available" if reason is None else "unavailable",
                        "reason": reason, "mean_test_net_return": float(np.mean([o["net_return"] for o in outcomes])) if outcomes else None,
                        "outcomes": outcomes, "correction": correction})
    included = sum(c.raw_p_value is not None for c in request.candidates)
    body = {"schema_version": "scanner_validation_v1", "input_fingerprint": panel["fingerprint"],
            "family_fingerprint": family_fp, "split_configuration_fingerprint": config_fp,
            "samples": [strip_datetimes(s) for s in samples], "folds": folds, "candidates": results,
            "family": {"declared_count": len(entries), "included_count": included,
                       "missing_ids": [c.candidate_id for c in request.candidates if c.raw_p_value is None],
                       "invalid_ids": [], "invalid_policy": "nonfinite/out-of-range requests rejected before execution",
                       "alpha": request.alpha, "methods": ["bonferroni", "holm", "bh"],
                       "provenance": "declared only; linking a value to this sample/hash does not verify a test"},
            "material": {"panel": panel["material"], "request": request.model_dump(mode="json")},
            "conventions": {"analysis_unit": "entire cross-section at one decision date",
                            "information_cutoff": "synthetic session UTC midnight; current scores/declarations only",
                            "execution": "weights[t] earn return[t+1], exactly one lag",
                            "cost": "sum(abs(w[t]-w[t-1])) * bps/10000 deducted once from return[t+1]",
                            "fold_boundaries": "each contiguous held-out block starts from cash; no terminal liquidation",
                            "wealth_stitching": False, "supervised_fit": False, "periods_per_year": 252},
            "unavailable_statistics": {"pbo": "no scanner CSCV/selection trial contract; purged folds are not PBO",
                                       "dsr": "trial population and selection assumptions are not established"},
            "caveats": ["Synthetic universe with disclosed reversal; no real alpha, official calendar or PIT certification.",
                        "Retrospective purged CV, not deployable chronological walk-forward; no supervised model is trained.",
                        "One whole cross-section per decision/outcome interval; assets at the same decision are never split.",
                        "Fixed daily dollar/sector policies only; beta/volatility validation is unavailable, not precomputed learned OOS.",
                        "Held-out blocks start from cash; turnover charges their entry once. No terminal liquidation at block end, matching finite-horizon scanner convention.",
                        "Nonadjacent blocks are not concatenated into wealth; outcomes/folds are not asserted independent.",
                        "Current available features may share historical price observations; no outcome-label fit or automatic winner.",
                        "All declared candidates remain visible. Corrections include only valid supplied p-values; partial family coverage is explicit.",
                        "BH requires independence/PRDS assumptions; no universal dependence guarantee or validated-alpha verdict.",
                        "Inline pinned material is downloadable research evidence, not a database registry or Phase 66 replay/restore support."]}
    body["result_fingerprint"] = digest(body)
    verify_validation_bundle(body)
    return body
