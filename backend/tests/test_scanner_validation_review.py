"""Independent interval, family-scope and public request-boundary regressions."""
from copy import deepcopy
import json

from fastapi.testclient import TestClient
import numpy as np
import pytest

from app.main import app
from app.run_replay.identity import digest
from app.scanner import validation
from app.scanner.validation import run_scanner_validation, verify_validation_bundle
from app.scanner_validation_routes import MAX_REQUEST_BYTES
from app.schemas import ScannerRequest


pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]
SECRET = "SYNTHETIC_PRIVATE_DECLARATION"


def request():
    return {"scanner": {"n_assets": 5, "start_date": "2023-01-02", "end_date": "2023-01-12",
                        "lookback_days": 1, "long_quantile": .4, "short_quantile": .4,
                        "cost_bps": 10.0}, "n_folds": 3, "embargo_days": 2.0,
            "candidates": [{"candidate_id": "fixed", "strategy": "cross_sectional_reversal",
                            "policy": {"mode": "dollar"}, "raw_p_value": .01}]}


def refuse_without_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid request reached scanner computation")
    monkeypatch.setattr(validation, "generate_sample_universe", forbidden)
    monkeypatch.setattr("app.main.run_scanner_backtest", forbidden)


@pytest.mark.parametrize("field,value", [
    ("n_assets", "5"), ("lookback_days", True), ("seed", False),
    ("gross_exposure", True), ("cost_bps", "10"), ("min_liquidity", False),
    ("long_quantile", "0.4"), ("unsupported_option", SECRET),
])
@pytest.mark.parametrize("endpoint", ["validation", "advanced"])
def test_new_scanner_requests_refuse_coercion_and_unknown_options(monkeypatch, endpoint, field, value):
    refuse_without_execution(monkeypatch)
    payload = request()
    payload["scanner"][field] = value
    if endpoint == "advanced":
        payload = {**payload["scanner"], "advanced_policy": {"mode": "dollar"}}
    path = "/scanner/validate" if endpoint == "validation" else "/scanner/backtest"
    response = TestClient(app).post(path, json=payload)
    assert response.status_code == 422
    assert SECRET not in response.text and len(response.content) < 500


def test_omitted_advanced_options_keep_legacy_request_coercion():
    parsed = ScannerRequest.model_validate({"n_assets": "5", "lookback_days": True,
                                            "cost_bps": "10", "legacy_ignored_option": "inert"})
    assert parsed.n_assets == 5 and parsed.lookback_days == 1 and parsed.cost_bps == 10
    assert parsed.advanced_policy is None and parsed.advanced_inputs is None


@pytest.mark.parametrize("endpoint", ["validation", "advanced"])
@pytest.mark.parametrize("defect", ["nested_extra", "offset_overflow"])
def test_nested_model_errors_are_private(monkeypatch, endpoint, defect):
    refuse_without_execution(monkeypatch)
    payload = request()
    inputs = {"exposures": [{"period": "2023-01-03", "asset_id": "STK001", "sector": "Tech",
                             "beta": 1.0, "eligible": True, "liquidity": .5,
                             "available_at": "2023-01-03T00:00:00Z"}]}
    if defect == "nested_extra":
        inputs["exposures"][0]["private_note"] = SECRET
    else:
        inputs["exposures"][0]["available_at"] = "0001-01-01T00:00:00+01:00"
        inputs["exposures"][0]["sector"] = SECRET
    payload["scanner"]["advanced_inputs"] = inputs
    if endpoint == "advanced":
        payload = {**payload["scanner"], "advanced_policy": {"mode": "dollar"}}
    path = "/scanner/validate" if endpoint == "validation" else "/scanner/backtest"
    response = TestClient(app).post(path, json=payload)
    assert response.status_code == 422
    assert SECRET not in response.text and len(response.content) < 500


@pytest.mark.parametrize("defect", ["duplicate_key", "nonfinite", "deep", "too_large"])
def test_validation_wire_input_is_bounded_and_unambiguous(monkeypatch, defect):
    refuse_without_execution(monkeypatch)
    raw = json.dumps(request())
    if defect == "duplicate_key":
        raw = raw[:-1] + ',"alpha":0.05,"alpha":0.1}'
    elif defect == "nonfinite":
        raw = raw[:-1] + ',"alpha":NaN}'
    elif defect == "deep":
        raw = '[' * 40 + '"' + SECRET + '"' + ']' * 40
    else:
        raw = '"' + SECRET + 'x' * MAX_REQUEST_BYTES + '"'
    response = TestClient(app).post("/scanner/validate", content=raw,
                                    headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert SECRET not in response.text and len(response.content) < 500


@pytest.mark.parametrize("field,value", [
    ("n_assets", 31), ("end_date", "2025-01-01"),
])
def test_validation_work_bounds_apply_before_generation(monkeypatch, field, value):
    refuse_without_execution(monkeypatch)
    payload = request()
    payload["scanner"][field] = value
    assert TestClient(app).post("/scanner/validate", json=payload).status_code == 422


def test_duplicate_candidate_family_is_refused_before_generation(monkeypatch):
    refuse_without_execution(monkeypatch)
    payload = request()
    payload["candidates"].append(deepcopy(payload["candidates"][0]))
    payload["candidates"][1]["raw_p_value"] = .2
    assert TestClient(app).post("/scanner/validate", json=payload).status_code == 422


def test_actual_closed_intervals_weekend_embargo_and_fold_entry(monkeypatch):
    calls = {name: 0 for name in ("normalize_samples", "purged_kfold", "audit_split", "adjust_p_values")}
    for name in calls:
        original = getattr(validation, name)
        def wrapped(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)
        monkeypatch.setattr(validation, name, wrapped)
    response = TestClient(app).post("/scanner/validate", json=request())
    assert response.status_code == 200, response.text
    result = response.json()
    assert verify_validation_bundle(result)
    assert calls == {"normalize_samples": 1, "purged_kfold": 1, "audit_split": 3, "adjust_p_values": 1}
    by_id = {s["sample_id"]: s["group"] for s in result["samples"]}
    expected = [
        {"test": ["03", "04", "05"], "purged": ["06"], "embargoed": [], "train": ["09", "10", "11"]},
        {"test": ["06", "09"], "purged": ["05", "10"], "embargoed": ["11"], "train": ["03", "04"]},
        {"test": ["10", "11"], "purged": ["09"], "embargoed": [], "train": ["03", "04", "05", "06"]},
    ]
    for fold, wanted in zip(result["folds"], expected):
        for membership, days in wanted.items():
            assert [by_id[sid] for sid in fold[membership + "_ids"]] == ["2023-01-" + d for d in days]
        assert fold["audit"]["valid"] and fold["audit"]["remaining_overlap_count"] == 0
        assert fold["trained_parameters"] == [] and fold["training_used_for_fit"] is False
    candidate = result["candidates"][0]
    assert candidate["status"] == "available" and len(candidate["outcomes"]) == 7
    panel = result["material"]["panel"]
    for fold in result["folds"]:
        previous = np.zeros(5)
        rows = [o for o in candidate["outcomes"] if o["fold"] == fold["label"]]
        for outcome in rows:
            weights = np.array([outcome["weights"][asset] for asset in panel["asset_ids"]])
            t = panel["sessions"].index(outcome["outcome_date"])
            gross = float(weights @ np.array(panel["returns"][t]))
            turnover = float(np.abs(weights - previous).sum())
            assert outcome["gross_return"] == pytest.approx(gross, abs=1e-14)
            assert outcome["turnover"] == pytest.approx(turnover, abs=1e-14)
            assert outcome["net_return"] == pytest.approx(gross - turnover * .001, abs=1e-14)
            previous = weights
    assert result["conventions"]["wealth_stitching"] is False


@pytest.mark.parametrize("field,value", [("long_quantile", .2), ("gross_exposure", .8), ("min_liquidity", 1.0)])
def test_family_identity_binds_actual_selection_settings(field, value):
    first = run_scanner_validation(request())
    changed = request()
    changed["scanner"][field] = value
    second = run_scanner_validation(changed)
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["candidates"][0]["outcomes"] != second["candidates"][0]["outcomes"]
    assert first["family_fingerprint"] != second["family_fingerprint"]
    assert first["result_fingerprint"] != second["result_fingerprint"]
    assert verify_validation_bundle(first) and verify_validation_bundle(second)


def test_rehashed_bundle_cannot_contradict_retained_family_scope():
    result = run_scanner_validation(request())
    result["material"]["request"]["scanner"]["gross_exposure"] = .8
    result["result_fingerprint"] = digest({k: v for k, v in result.items() if k != "result_fingerprint"})
    with pytest.raises(ValueError, match="family/request fingerprint"):
        verify_validation_bundle(result)


def test_missing_declared_p_value_is_distinct_from_zero():
    payload = request()
    payload["candidates"][0]["raw_p_value"] = 0.0
    missing = deepcopy(payload["candidates"][0])
    missing.update(candidate_id="missing", raw_p_value=None)
    payload["candidates"].append(missing)
    result = run_scanner_validation(payload)
    assert result["family"]["declared_count"] == 2 and result["family"]["included_count"] == 1
    assert result["family"]["missing_ids"] == ["missing"]
    zero, absent = [c["correction"] for c in result["candidates"]]
    assert zero["raw_p_value"] == zero["bonferroni"] == zero["holm"] == zero["bh"] == 0
    assert zero["provenance_status"] == "declared" and zero["state_raw"] == "below_threshold"
    assert absent["raw_p_value"] is None and absent["holm"] is None
    assert absent["state_raw"] == "unavailable"


def test_typed_openapi_and_get_remain_read_only(monkeypatch):
    refuse_without_execution(monkeypatch)
    client = TestClient(app)
    assert client.get("/scanner/validate").status_code == 405
    schema = app.openapi()["paths"]["/scanner/validate"]["post"]["requestBody"]
    assert schema["content"]["application/json"]["schema"]["$ref"].endswith("/ScannerValidationRequest")
