"""Public-API source-to-stress bridge, with only test-owned SQLite access."""

from datetime import date, timedelta

import pytest


@pytest.mark.parametrize("ids", [("a", "b"), ("constructor", "__proto__")])
def test_explicit_source_composer_to_stress(isolated_lab_db, ids):
    # The protected fixture/runner is installed before importing the application.
    from fastapi.testclient import TestClient
    from app.main import app

    a, b = ids
    timestamps = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(24)]
    payload = {
        "name": "Explicit Composer source", "frequency": "daily",
        "timestamps": timestamps,
        "assets": [
            {"asset_id": a, "returns": [((i * 3 % 11) - 5) / 1000 for i in range(24)]},
            {"asset_id": b, "returns": [((i * 4 % 11) - 5) / 1000 for i in range(24)]},
        ],
        "weights": {a: 0.7, b: 0.3}, "method": "user_supplied",
        "normalization": "none", "weight_provenance": {"basis": "declared"},
        "covariance": {"method": "sample", "repair": "none"},
        "constraints": {"long_only": True, "min_weight": 0, "max_weight": 1,
                        "net_exposure_target": 1, "gross_exposure_limit": 1,
                        "cash_residual_allowed": False},
        "rebalance": {"kind": "one_time", "initial_turnover_policy": "none"},
        "estimation": {"mode": "rolling", "lookback": 20, "lag": 1},
    }
    with TestClient(app) as client:
        created = client.post("/portfolio-diagnostics/runs", json=payload)
        assert created.status_code == 201, created.text
        run_id = created.json()["id"]
        assert type(run_id) is int and run_id > 0
        done = client.post(f"/portfolio-diagnostics/runs/{run_id}/execute",
                           json={"create_experiment": False})
        assert done.status_code == 200, done.text
        source = client.get(f"/portfolio-diagnostics/runs/{run_id}").json()
        assert source["id"] == run_id and source["status"] == "completed"
        assert source["solver_status"] == "closed_form"
        assert source["integrity_status"] == "declared"
        assert source["experiment_id"] is None
        assert source["configuration"]["user_provenance"] == {"basis": "declared", "lag": None}
        assert source["configuration"]["user_weights"] == {a: 0.7, b: 0.3}
        assert source["configuration"]["normalization"] == "none"
        before_rows = client.get(f"/portfolio-diagnostics/runs/{run_id}/rebalances").json()
        assert len(before_rows["items"]) == 1
        rebalance = before_rows["items"][0]
        assert rebalance["rebalance_id"] == 0
        assert rebalance["weights"] == {a: 0.7, b: 0.3}
        assert rebalance["window_start"] == 0 and rebalance["window_end"] == 19
        assert rebalance["decision_timestamp"] == timestamps[20]
        assert rebalance["effective_timestamp"] == timestamps[20]
        assert rebalance["turnover"] is None
        assert rebalance["weight_fingerprint"]

        stress = client.post("/portfolio-stress/runs", json={
            "name": "Hand-checkable stress", "portfolio_run_id": run_id,
            "portfolio_rebalance_id": 0,
            "scenario": {"scenario_definition_id": "ui_asset_shock_v1",
                         "name": "Hand-checkable stress",
                         "scenario_type": "hypothetical_asset_shock", "source": "user",
                         "missing_shock_policy": "unavailable",
                         "asset_shocks": {a: {"value": -10, "unit": "percent"},
                                          b: {"value": 0, "unit": "percent"}}},
        })
        assert stress.status_code == 201, stress.text
        stress_id = stress.json()["id"]
        executed = client.post(f"/portfolio-stress/runs/{stress_id}/execute",
                               json={"create_experiment": False})
        assert executed.status_code == 200, executed.text
        stored_stress = client.get(f"/portfolio-stress/runs/{stress_id}").json()
        assert stored_stress["status"] == "completed"
        assert stored_stress["scenario_return"] == pytest.approx(-0.07)
        assert stored_stress["scenario_pnl"] is None
        assert stored_stress["experiment_id"] is None
        assert stored_stress["portfolio_run_id"] == run_id
        assert stored_stress["portfolio_rebalance_id"] == 0
        assert stored_stress["baseline_weight_fingerprint"] == rebalance["weight_fingerprint"]
        identity = stored_stress["configuration"]["portfolio_identity"]
        assert identity["portfolio_run_id"] == run_id and identity["rebalance_id"] == 0
        assert identity["weight_fingerprint"] == rebalance["weight_fingerprint"]
        assert identity["portfolio_configuration_fingerprint"] == source["configuration_fingerprint"]
        assert identity["portfolio_universe_fingerprint"] == source["universe_fingerprint"]
        assert identity["covariance_fingerprint"] == rebalance["covariance_fingerprint"]
        assert client.get(f"/portfolio-diagnostics/runs/{run_id}").json() == source
        assert client.get(f"/portfolio-diagnostics/runs/{run_id}/rebalances").json() == before_rows
