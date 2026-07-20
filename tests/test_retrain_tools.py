import json

import pytest

from omen.retrain.retrain_tools import (
    record_deployment,
    load_deployment_manifest,
    compare_candidate_to_deployed,
    execute_redeploy,
)


def test_record_and_load_deployment_manifest_round_trip(tmp_path):
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("date,value\n2024-01-01,1.0\n")

    write_result = record_deployment(
        str(csv_path),
        model="SARIMA",
        params={"order": [1, 1, 1], "seasonal_order": [1, 1, 1, 7]},
        backtest_metrics={"mae": 5.0, "rmse": 6.0, "mape_pct": 4.2},
        horizon=30,
    )
    assert write_result["status"] == "ok"

    loaded = load_deployment_manifest(str(csv_path))
    assert loaded["model"] == "SARIMA"
    assert loaded["backtest_metrics"]["mape_pct"] == 4.2
    assert loaded["horizon"] == 30


def test_load_deployment_manifest_errors_when_nothing_recorded(tmp_path):
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("date,value\n2024-01-01,1.0\n")

    result = load_deployment_manifest(str(csv_path))
    assert "error" in result


def test_record_deployment_respects_explicit_manifest_path(tmp_path):
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("date,value\n2024-01-01,1.0\n")
    manifest_path = tmp_path / "custom_manifest.json"

    record_deployment(
        str(csv_path),
        model="ETS",
        params={},
        backtest_metrics={"mape_pct": 3.0},
        horizon=14,
        manifest_path=str(manifest_path),
    )
    assert manifest_path.exists()
    assert json.loads(manifest_path.read_text())["model"] == "ETS"


def test_record_deployment_overwrites_previous_manifest(tmp_path):
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("date,value\n2024-01-01,1.0\n")

    record_deployment(str(csv_path), model="ETS", params={}, backtest_metrics={"mape_pct": 5.0}, horizon=14)
    record_deployment(str(csv_path), model="SARIMA", params={}, backtest_metrics={"mape_pct": 4.0}, horizon=30)

    loaded = load_deployment_manifest(str(csv_path))
    assert loaded["model"] == "SARIMA"
    assert loaded["horizon"] == 30


def test_compare_candidate_to_deployed_recommends_redeploy_above_threshold():
    result = compare_candidate_to_deployed(
        candidate_metrics={"mape_pct": 4.0},
        deployed_metrics={"mape_pct": 5.0},
        improvement_threshold_pct=10.0,
    )
    assert result["should_redeploy"] is True
    assert result["pct_improvement"] == 20.0


def test_compare_candidate_to_deployed_rejects_marginal_improvement():
    result = compare_candidate_to_deployed(
        candidate_metrics={"mape_pct": 4.8},
        deployed_metrics={"mape_pct": 5.0},
        improvement_threshold_pct=10.0,
    )
    assert result["should_redeploy"] is False


def test_compare_candidate_to_deployed_rejects_worse_candidate():
    result = compare_candidate_to_deployed(
        candidate_metrics={"mape_pct": 6.0},
        deployed_metrics={"mape_pct": 5.0},
    )
    assert result["should_redeploy"] is False
    assert result["pct_improvement"] < 0


def test_compare_candidate_to_deployed_errors_on_missing_metric():
    result = compare_candidate_to_deployed(
        candidate_metrics={"mae": 1.0},
        deployed_metrics={"mape_pct": 5.0},
    )
    assert "error" in result


def test_execute_redeploy_refuses_without_confirmation(tmp_path):
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("date,value\n2024-01-01,1.0\n")

    result = execute_redeploy(
        str(csv_path),
        model_type="sarima",
        params={},
        horizon=30,
        backtest_metrics={"mape_pct": 5.0},
        confirmed=False,
    )
    assert result["status"] == "not_executed"
    assert "error" in result
    assert not (tmp_path / "deployment_manifest.json").exists()


def test_execute_redeploy_rejects_unknown_model_type(tmp_path):
    csv_path = tmp_path / "series.csv"
    csv_path.write_text("date,value\n2024-01-01,1.0\n")

    result = execute_redeploy(
        str(csv_path),
        model_type="prophet",
        params={},
        horizon=30,
        backtest_metrics={"mape_pct": 5.0},
        confirmed=True,
    )
    assert "error" in result


def test_execute_redeploy_retrains_and_records_manifest(tmp_path):
    pytest.importorskip("statsmodels")
    pytest.importorskip("sklearn")

    from omen.data_prep import generate_synthetic_series

    csv_path = tmp_path / "series.csv"
    generate_synthetic_series(n_days=200).to_csv(csv_path, index=False)

    result = execute_redeploy(
        str(csv_path),
        model_type="sarima",
        params={"order": [1, 1, 1], "seasonal_order": [1, 1, 1, 7]},
        horizon=10,
        backtest_metrics={"mape_pct": 4.5},
        confirmed=True,
    )
    assert result["status"] == "redeployed"
    assert len(result["forecast_result"]["forecast"]) == 10
    assert result["manifest"]["model"] == "SARIMA"

    loaded = load_deployment_manifest(str(csv_path))
    assert loaded["backtest_metrics"]["mape_pct"] == 4.5
    assert loaded["horizon"] == 10
