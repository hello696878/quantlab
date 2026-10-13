"""Real scanner selections, purged membership, declared family and API boundaries."""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scanner.validation import ScannerValidationRequest, run_scanner_validation, verify_validation_bundle

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


def request():
    return {"scanner": {"n_assets": 20, "start_date": "2023-01-01", "end_date": "2023-04-30",
                        "lookback_days": 3, "long_quantile": .4, "short_quantile": .4, "cost_bps": 10.0},
            "candidates": [{"candidate_id": cid, "strategy": "cross_sectional_reversal", "policy": {"mode": mode}, "raw_p_value": p}
                           for cid, mode, p in [("d", "dollar", .01), ("s", "sector", .04), ("b", "beta", .20)]]}


def test_end_to_end_actual_selections_and_purged_audit():
    result = run_scanner_validation(request())
    assert verify_validation_bundle(result)
    assert len(result["folds"]) == 3
    samples = {s["sample_id"]: s for s in result["samples"]}
    for fold in result["folds"]:
        assert fold["audit"]["valid"] and fold["audit"]["remaining_overlap_count"] == 0
        assert not set(fold["train_ids"]) & set(fold["test_ids"])
        assert not set(fold["train_ids"]) & set(fold["purged_ids"])
        assert fold["trained_parameters"] == [] and fold["training_used_for_fit"] is False
        for train in fold["train_ids"]:
            for test in fold["test_ids"]:
                a, b = samples[train], samples[test]
                assert a["evaluation_time"] < b["prediction_time"] or b["evaluation_time"] < a["prediction_time"]
    candidate = result["candidates"][0]
    assert candidate["status"] == "available"
    panel = result["material"]["panel"]
    returns = np.asarray(panel["returns"])
    outcomes = candidate["outcomes"]
    assert len(outcomes) == len(samples)
    assert any(any(w != 0 for w in o["weights"].values()) for o in outcomes)
    for o in outcomes:
        t = panel["sessions"].index(o["outcome_date"])
        expected_gross = sum(o["weights"][a] * returns[t, j] for j, a in enumerate(panel["asset_ids"]))
        assert o["gross_return"] == pytest.approx(expected_gross)
        assert o["cost"] == pytest.approx(o["turnover"] * .001)
        assert o["net_return"] == pytest.approx(expected_gross - o["cost"])
        assert o["sample_id"] in samples
    for fold in result["folds"]:
        first = next(o for o in outcomes if o["fold"] == fold["label"])
        assert first["turnover"] == pytest.approx(sum(abs(w) for w in first["weights"].values()))
    assert result["candidates"][2]["status"] == "unavailable"
    assert "frozen estimation" in result["candidates"][2]["reason"]
    assert result["candidates"][2]["outcomes"] == []
    assert result["unavailable_statistics"]["pbo"]


def test_hand_declared_p_family_mapping_and_missing():
    result = run_scanner_validation(request())
    rows = [c["correction"] for c in result["candidates"]]
    assert [r["candidate_id"] for r in rows] == ["d", "s", "b"]
    np.testing.assert_allclose([r["bonferroni"] for r in rows], [.03, .12, .60])
    np.testing.assert_allclose([r["holm"] for r in rows], [.03, .08, .20])
    assert all(r["provenance_status"] == "declared" for r in rows)
    altered = request()
    altered["candidates"][1]["raw_p_value"] = None
    partial = run_scanner_validation(altered)
    assert partial["family"]["declared_count"] == 3 and partial["family"]["included_count"] == 2
    assert partial["family"]["missing_ids"] == ["s"]
    assert partial["candidates"][1]["correction"]["holm"] is None
    assert partial["family_fingerprint"] != result["family_fingerprint"]


def test_learned_policies_are_never_fitted_then_relabelled_oos(monkeypatch):
    payload = request()
    payload["candidates"] = [payload["candidates"][2]]
    monkeypatch.setattr("app.scanner.validation.advanced_weights", lambda *a, **k: pytest.fail("learned policy must not execute in validation"))
    beta = run_scanner_validation(payload)
    assert beta["candidates"][0]["status"] == "unavailable"
    payload["candidates"][0]["policy"] = {"mode": "dollar", "volatility": {"target": .2}}
    vol = run_scanner_validation(payload)
    assert vol["candidates"][0]["status"] == "unavailable"


def test_tamper_and_determinism():
    a, b = run_scanner_validation(request()), run_scanner_validation(request())
    assert a == b
    a["material"]["panel"]["prices"][0][0] += 1
    with pytest.raises(ValueError, match="fingerprint"):
        verify_validation_bundle(a)


@pytest.mark.parametrize("change", ["family", "n_assets", "date_range", "nonfinite", "bool", "combined", "folds"])
def test_bounded_invalid_validation_requests(change):
    value = request()
    if change == "family": value["candidates"] *= 5
    if change == "n_assets": value["scanner"]["n_assets"] = 31
    if change == "date_range": value["scanner"]["end_date"] = "2030-01-01"
    if change == "nonfinite": value["candidates"][0]["raw_p_value"] = "nan"
    if change == "bool": value["alpha"] = True
    if change == "combined": value["candidates"][0]["policy"]["mode"] = "sector_beta"
    if change == "folds": value["n_folds"] = 9
    # Pure routes do not require the application's database-initializing lifespan.
    client = TestClient(app)
    response = client.post("/scanner/validate", json=value)
    assert response.status_code == 422


def test_endpoint_shapes_and_no_get_computation():
    client = TestClient(app)
    response = client.post("/scanner/validate", json=request())
    assert response.status_code == 200, response.text
    assert verify_validation_bundle(response.json())
    assert client.get("/scanner/validate").status_code == 405
    result = client.post("/scanner/backtest", json={**request()["scanner"], "advanced_policy": {"mode": "sector"}})
    assert result.status_code == 200, result.text
    assert result.json()["advanced"]["policy"]["mode"] == "sector"
    assert result.json()["advanced"]["diagnostics"]
