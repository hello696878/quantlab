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


def _derived_payload(method):
    patterns = ((-0.001, 0.001, -0.001, 0.001),
                (-0.002, -0.002, 0.002, 0.002))
    return {
        "name": "Derived Composer source", "frequency": "daily",
        "timestamps": [(date(2024, 1, 1) + timedelta(days=i)).isoformat()
                       for i in range(24)],
        "assets": [{"asset_id": asset_id,
                    "returns": [patterns[j][i % 4] for i in range(24)]}
                   for j, asset_id in enumerate(("a", "b"))],
        "method": method, "normalization": "sum_to_one",
        "covariance": {"method": "sample", "repair": "none"},
        "constraints": {"long_only": True, "min_weight": 0, "max_weight": 1,
                        "net_exposure_target": 1, "gross_exposure_limit": 1,
                        "cash_residual_allowed": False},
        "rebalance": {"kind": "one_time", "initial_turnover_policy": "none"},
        "estimation": {"mode": "rolling", "lookback": 20, "lag": 1},
    }


def _execute_source(client, payload):
    assert not {"weights", "weight_provenance", "volatility_floor"} & payload.keys()
    created = client.post("/portfolio-diagnostics/runs", json=payload)
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    assert type(run_id) is int and run_id > 0
    done = client.post(f"/portfolio-diagnostics/runs/{run_id}/execute",
                       json={"create_experiment": False})
    assert done.status_code == 200, done.text
    read = client.get(f"/portfolio-diagnostics/runs/{run_id}")
    assert read.status_code == 200, read.text
    source = read.json()
    assert source["id"] == run_id and source["status"] == "completed"
    assert source["method"] == payload["method"]
    assert source["experiment_id"] is None
    config = source["configuration"]
    assert config["user_weights"] is None and config["user_provenance"] is None
    assert config["volatility_floor"] is None
    assert config["normalization"] == "sum_to_one"
    rows = client.get(f"/portfolio-diagnostics/runs/{run_id}/rebalances")
    assert rows.status_code == 200, rows.text
    assert len(rows.json()["items"]) == 1
    rebalance = rows.json()["items"][0]
    assert rebalance["rebalance_id"] == 0
    assert (rebalance["window_start"], rebalance["window_end"]) == (0, 19)
    assert rebalance["effective_timestamp"] == payload["timestamps"][20]
    assert rebalance["decision_timestamp"] == payload["timestamps"][20]
    assert rebalance["turnover"] is None
    return source, rows.json()


@pytest.mark.parametrize("method, expected", [
    ("equal_weight", {"a": 0.5, "b": 0.5}),
    ("inverse_volatility", {"a": 2 / 3, "b": 1 / 3}),
])
def test_derived_source_composer_to_stress(isolated_lab_db, method, expected):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        source, before_rows = _execute_source(client, _derived_payload(method))
        run_id = source["id"]
        rebalance = before_rows["items"][0]
        assert source["solver_status"] == "closed_form"
        assert source["integrity_status"] == "verified_causal_rolling"
        assert rebalance["status"] == "completed"
        assert rebalance["weights"] == pytest.approx(expected)
        assert rebalance["solver"]["unavailable_assets"] == []
        assert rebalance["solver"]["floored_assets"] == []
        assert rebalance["constraint_violation_count"] == 0
        assert rebalance["weight_fingerprint"]

        stress = client.post("/portfolio-stress/runs", json={
            "name": "Derived source shock", "portfolio_run_id": run_id,
            "portfolio_rebalance_id": 0,
            "scenario": {"scenario_definition_id": "ui_asset_shock_v1",
                         "name": "Derived source shock",
                         "scenario_type": "hypothetical_asset_shock", "source": "user",
                         "missing_shock_policy": "unavailable",
                         "asset_shocks": {"a": {"value": -10, "unit": "percent"},
                                          "b": {"value": 0, "unit": "percent"}}},
        })
        assert stress.status_code == 201, stress.text
        stress_id = stress.json()["id"]
        executed = client.post(f"/portfolio-stress/runs/{stress_id}/execute",
                               json={"create_experiment": False})
        assert executed.status_code == 200, executed.text
        stored = client.get(f"/portfolio-stress/runs/{stress_id}")
        assert stored.status_code == 200, stored.text
        result = stored.json()
        assert result["status"] == "completed" and result["experiment_id"] is None
        assert result["scenario_return"] == pytest.approx(-0.1 * expected["a"])
        assert result["scenario_pnl"] is None
        assert result["portfolio_run_id"] == run_id
        assert result["portfolio_rebalance_id"] == 0
        assert result["baseline_weight_fingerprint"] == rebalance["weight_fingerprint"]
        identity = result["configuration"]["portfolio_identity"]
        assert identity["portfolio_run_id"] == run_id and identity["rebalance_id"] == 0
        assert identity["weight_fingerprint"] == rebalance["weight_fingerprint"]
        assert identity["portfolio_configuration_fingerprint"] == source["configuration_fingerprint"]
        assert identity["portfolio_universe_fingerprint"] == source["universe_fingerprint"]
        assert identity["covariance_fingerprint"] == rebalance["covariance_fingerprint"]
        assert client.get(f"/portfolio-diagnostics/runs/{run_id}").json() == source
        assert client.get(f"/portfolio-diagnostics/runs/{run_id}/rebalances").json() == before_rows


def test_initial_inverse_weights_ignore_future_only_mutation(isolated_lab_db):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        original, before_rows = _execute_source(client, _derived_payload("inverse_volatility"))
        mutated = _derived_payload("inverse_volatility")
        mutated["assets"][0]["returns"][20:] = [0.2, -0.1, 0.3, 0.1]
        mutated["assets"][1]["returns"][20:] = [-0.1, 0.4, 0.1, -0.2]
        changed, after_rows = _execute_source(client, mutated)
        assert changed["id"] != original["id"]
        assert after_rows["items"][0]["weights"] == before_rows["items"][0]["weights"]
        assert after_rows["items"][0]["weights"] == pytest.approx({"a": 2 / 3, "b": 1 / 3})
        assert after_rows["items"][0]["weight_fingerprint"] == before_rows["items"][0]["weight_fingerprint"]
        assert client.get(f"/portfolio-diagnostics/runs/{original['id']}").json() == original


@pytest.mark.parametrize("all_unusable", [False, True])
def test_inverse_unusable_volatility_is_reported_without_floor(isolated_lab_db, all_unusable):
    from fastapi.testclient import TestClient
    from app.main import app

    payload = _derived_payload("inverse_volatility")
    payload["assets"][0]["returns"] = [0.0] * 24
    if all_unusable:
        payload["assets"][1]["returns"] = [0.0] * 24
    with TestClient(app) as client:
        source, rows = _execute_source(client, payload)
        rebalance = rows["items"][0]
        unavailable = rebalance["solver"]["unavailable_assets"]
        assert unavailable == [
            {"asset_id": asset_id, "reason": "zero or negative volatility with no configured floor"}
            for asset_id in (["a", "b"] if all_unusable else ["a"])
        ]
        assert rebalance["solver"]["floored_assets"] == []
        assert any("volatility unavailable for a" in warning for warning in source["warnings"])
        if all_unusable:
            assert source["solver_status"] == "failed"
            assert rebalance["status"] == "failed" and rebalance["weights"] is None
            assert rebalance["reason"] == "no asset has a usable volatility"
            assert source["risk"] is None
            assert any("no rebalance produced weights" in warning for warning in source["warnings"])
        else:
            assert source["solver_status"] == "closed_form"
            assert rebalance["status"] == "completed"
            assert rebalance["weights"] == {"a": 0.0, "b": 1.0}


def test_return_data_reuse_from_actual_stored_universe(isolated_lab_db):
    # The fixture and protected runner install isolation before application import.
    from fastapi.testclient import TestClient
    from app.main import app

    source_payload = _derived_payload("user_supplied")
    source_payload.update({
        "name": "Nondefault source book", "weights": {"a": 0.7, "b": 0.3},
        "weight_provenance": {"basis": "declared"}, "normalization": "none",
        "estimation": {"mode": "rolling", "lookback": 5, "lag": 1},
        "rebalance": {"kind": "one_time", "initial_turnover_policy": "zero_book"},
        "solver": {"tolerance": 0.0001, "max_iterations": 40},
        "volatility_floor": 0.001, "cost_notional": 1000,
    })
    source_payload["constraints"]["max_weight"] = 0.8
    source_payload["assets"].reverse()
    for asset in source_payload["assets"]:
        asset.update(name=f"  Stored {asset['asset_id']}  ", currency="USD", group="research")

    with TestClient(app) as client:
        response = client.post("/portfolio-diagnostics/runs", json=source_payload)
        assert response.status_code == 201, response.text
        source_id = response.json()["id"]
        executed = client.post(f"/portfolio-diagnostics/runs/{source_id}/execute",
                               json={"create_experiment": False})
        assert executed.status_code == 200, executed.text
        baseline = client.post(f"/portfolio-diagnostics/runs/{source_id}/mark-baseline", json={})
        assert baseline.status_code == 200, baseline.text
        fetched = client.get(f"/portfolio-diagnostics/runs/{source_id}")
        assert fetched.status_code == 200, fetched.text
        source = fetched.json()
        assert source["status"] == "completed" and source["is_baseline"] is True
        before_rows = client.get(f"/portfolio-diagnostics/runs/{source_id}/rebalances").json()
        stored = source["universe"]
        assert all(stored[key] is None for key in ("benchmark_returns", "prior_weights", "sample_ids"))
        assert all(asset["integer_lots"] is False and asset["metadata"] == {} for asset in stored["assets"])
        assert [asset["asset_id"] for asset in stored["assets"]] == ["b", "a"]

        # Derive every data field from the GET, not from the original create payload.
        return_input = {
            "frequency": stored["frequency"], "timestamps": stored["timestamps"],
            "assets": [{key: asset[key] for key in ("asset_id", "returns", "name", "asset_type", "group", "currency")}
                       for asset in stored["assets"]],
        }
        fresh = {
            **return_input, "name": "Fresh construction from stored data", "method": "equal_weight",
            "normalization": "sum_to_one", "covariance": {"method": "sample", "repair": "none"},
            "estimation": {"mode": "rolling", "lookback": 20, "lag": 1},
            "constraints": {"long_only": True, "min_weight": 0, "max_weight": 1,
                            "net_exposure_target": 1, "gross_exposure_limit": 1,
                            "cash_residual_allowed": False},
            "rebalance": {"kind": "one_time", "initial_turnover_policy": "none"},
        }
        created = client.post("/portfolio-diagnostics/runs", json=fresh)
        assert created.status_code == 201, created.text
        new_id = created.json()["id"]
        assert new_id > 0 and new_id != source_id
        done = client.post(f"/portfolio-diagnostics/runs/{new_id}/execute", json={"create_experiment": False})
        assert done.status_code == 200, done.text
        new = client.get(f"/portfolio-diagnostics/runs/{new_id}").json()
        assert new["status"] == "completed" and new["method"] == "equal_weight"
        assert new["name"] == fresh["name"] and new["is_baseline"] is False
        assert new["universe"] == stored
        assert [asset["returns"] for asset in new["universe"]["assets"]] == [asset["returns"] for asset in stored["assets"]]
        assert [asset["name"] for asset in new["universe"]["assets"]] == ["  Stored b  ", "  Stored a  "]
        config = new["configuration"]
        assert config["estimation"] == {"mode": "rolling", "lookback": 20, "lag": 1}
        assert config["constraints"]["max_weight"] == 1
        assert config["rebalance"] == {"kind": "one_time", "initial_turnover_policy": "none"}
        assert config["solver"] == {"tolerance": 1e-6, "max_iterations": 2000}
        assert config["normalization"] == "sum_to_one"
        assert config["user_weights"] is None and config["user_provenance"] is None
        assert config["volatility_floor"] is None and config["cost_notional"] is None
        assert config["linked_fingerprints"] == {} and config["validation_split_label"] is None
        for key in ("dataset_version_id", "validation_run_id", "regime_run_id", "regime_definition_id",
                    "cost_diagnostic_run_id", "overfitting_run_id", "experiment_id"):
            assert new[key] is None
        assert new["configuration_fingerprint"] != source["configuration_fingerprint"]
        assert new["result_fingerprint"] != source["result_fingerprint"]
        new_rows = client.get(f"/portfolio-diagnostics/runs/{new_id}/rebalances").json()["items"]
        assert new_rows[0]["weights"] == {"b": 0.5, "a": 0.5}
        assert (new_rows[0]["window_start"], new_rows[0]["window_end"]) == (0, 19)
        assert new_rows[0]["effective_timestamp"] == stored["timestamps"][20]
        assert new_rows[0]["turnover"] is None
        assert client.get(f"/portfolio-diagnostics/runs/{source_id}").json() == source
        assert client.get(f"/portfolio-diagnostics/runs/{source_id}/rebalances").json() == before_rows
