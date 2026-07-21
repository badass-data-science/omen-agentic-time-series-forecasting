import pandas as pd
import pytest

pytest.importorskip("statsmodels")
pytest.importorskip("sklearn")

from omen.data_prep import generate_synthetic_series
from omen.deploy.forecast_tools import (
    forecast_naive,
    forecast_ets,
    forecast_sarima,
    forecast_gradient_boosted_trees,
    forecast_ensemble,
)


@pytest.fixture
def sample_df():
    return generate_synthetic_series(n_days=300)


def test_forecast_naive_extends_beyond_last_date(sample_df):
    result = forecast_naive(sample_df, horizon=10)
    last_observed = str(sample_df["date"].iloc[-1].date())
    first_forecast_date = result["forecast"][0]["date"]
    assert first_forecast_date > last_observed


def test_forecast_naive_truncates_long_horizons(sample_df):
    result = forecast_naive(sample_df, horizon=100)
    assert result["truncated"] is True
    assert len(result["forecast"]) <= 61  # cap + 1 note entry


def test_forecast_naive_has_analytic_interval_flat(sample_df):
    result = forecast_naive(sample_df, horizon=10, method="naive")
    row = result["forecast"][0]
    assert "lower" in row and "upper" in row
    assert row["lower"] <= row["forecast"] <= row["upper"]
    assert "residual" in result["interval_note"].lower()


def test_forecast_naive_has_analytic_interval_seasonal(sample_df):
    result = forecast_naive(sample_df, horizon=10, method="seasonal_naive")
    row = result["forecast"][0]
    assert "lower" in row and "upper" in row
    assert row["lower"] <= row["forecast"] <= row["upper"]


def test_forecast_naive_interval_widens_with_horizon(sample_df):
    result = forecast_naive(sample_df, horizon=20, method="naive")
    first_width = result["forecast"][0]["upper"] - result["forecast"][0]["lower"]
    last_width = result["forecast"][-1]["upper"] - result["forecast"][-1]["lower"]
    assert last_width > first_width


def test_forecast_naive_insufficient_history_is_point_only():
    # generate_synthetic_series requires n_days >= 3 (its anomaly injection
    # samples without replacement), so build a bare 2-row series directly
    # for this too-short-for-a-residual-std edge case.
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=2), "value": [100.0, 102.0]})
    result = forecast_naive(df, horizon=5, method="naive")
    assert "lower" not in result["forecast"][0]
    assert "not enough history" in result["interval_note"].lower()


def test_forecast_ets_has_interval_note(sample_df):
    result = forecast_ets(sample_df, horizon=10)
    assert "interval_note" in result
    assert "aicc" in result


def test_forecast_sarima_has_analytic_interval(sample_df):
    result = forecast_sarima(sample_df, horizon=10)
    assert "lower" in result["forecast"][0]
    assert "upper" in result["forecast"][0]
    assert "aicc" in result


def test_forecast_gbt_flags_compounding_error_caveat(sample_df):
    result = forecast_gradient_boosted_trees(sample_df, horizon=10, n_bootstrap=0)
    assert "caveat" in result
    assert "recursive" in result["caveat"].lower() or "compound" in result["caveat"].lower()


def test_forecast_gbt_has_quantile_interval(sample_df):
    result = forecast_gradient_boosted_trees(sample_df, horizon=10, n_bootstrap=0)
    row = result["forecast"][0]
    assert "lower" in row and "upper" in row
    assert row["lower"] <= row["forecast"] <= row["upper"]
    assert "quantile" in result["interval_note"].lower()


def test_forecast_gbt_interval_never_crosses(sample_df):
    result = forecast_gradient_boosted_trees(sample_df, horizon=30, n_bootstrap=0)
    for row in result["forecast"]:
        if "forecast" in row:
            assert row["lower"] <= row["upper"]


def test_forecast_gbt_feature_importance_ci_shape(sample_df):
    result = forecast_gradient_boosted_trees(sample_df, horizon=10, n_bootstrap=10)
    assert result["feature_importance_ci_n_bootstrap"] == 10
    assert result["feature_importance_ci_confidence_level"] == 0.95
    for col, entry in result["feature_importances"].items():
        assert set(entry.keys()) == {"importance", "ci_lower", "ci_upper"}
        assert entry["ci_lower"] <= entry["ci_upper"]


def test_forecast_gbt_feature_importance_ci_skipped_when_n_bootstrap_zero(sample_df):
    result = forecast_gradient_boosted_trees(sample_df, horizon=10, n_bootstrap=0)
    assert result["feature_importance_ci_n_bootstrap"] == 0
    for entry in result["feature_importances"].values():
        assert entry["ci_lower"] is None
        assert entry["ci_upper"] is None
        assert entry["importance"] is not None


@pytest.mark.parametrize(
    "forecast_fn,kwargs",
    [
        (forecast_naive, {}),
        (forecast_ets, {}),
        (forecast_sarima, {}),
        (forecast_gradient_boosted_trees, {"n_bootstrap": 0}),
    ],
)
def test_all_forecast_tools_include_plausibility_check(sample_df, forecast_fn, kwargs):
    result = forecast_fn(sample_df, horizon=10, **kwargs)
    check = result["plausibility_check"]
    assert "forecast_endpoint_change" in check
    assert "historical_min" in check and "historical_max" in check
    assert "goes_below_historical_min" in check and "goes_above_historical_max" in check
    assert "interpretation" in check


def test_plausibility_check_flags_extreme_forecast():
    # A flat series with essentially no historical variability, whose
    # naive forecast is likewise flat, should NOT be flagged extreme.
    df = generate_synthetic_series(n_days=200, trend_per_day=0.0, weekly_amplitude=0.0, yearly_amplitude=0.0, noise_std=0.5)
    result = forecast_naive(df, horizon=10, method="naive")
    check = result["plausibility_check"]
    assert check["is_extreme_relative_to_history"] is False


def test_plausibility_check_insufficient_history():
    df = generate_synthetic_series(n_days=15)
    result = forecast_naive(df, horizon=30, method="naive")
    check = result["plausibility_check"]
    assert check["endpoint_change_z_score"] is None
    assert "not enough history" in check["interpretation"].lower()


def test_forecast_ensemble_combines_two_models(sample_df):
    result = forecast_ensemble(sample_df, model_types=["ets", "sarima"], horizon=10)
    assert result["horizon"] == 10
    assert len(result["components"]) == 2
    assert "forecast" in result
    assert "plausibility_check" in result


def test_forecast_ensemble_weighted_average_matches_manual_computation(sample_df):
    result = forecast_ensemble(sample_df, model_types=["naive", "naive"], horizon=5, weights=[3, 1])
    single = forecast_naive(sample_df, horizon=5)
    single_values = [row["forecast"] for row in single["forecast"]]
    ensemble_values = [row["forecast"] for row in result["forecast"]]
    # Both components are identical naive forecasts, so the weighted
    # average must equal the plain naive forecast regardless of weights.
    for e, s in zip(ensemble_values, single_values):
        assert e == pytest.approx(s, abs=1e-2)


def test_forecast_ensemble_naive_now_contributes_an_interval(sample_df):
    # naive used to be the one model_type with zero interval capability,
    # ever -- now that it has an analytic one (given enough history), an
    # ensemble combining it with another interval-bearing model should
    # get a combined interval too.
    result = forecast_ensemble(sample_df, model_types=["naive", "sarima"], horizon=10)
    assert "lower" in result["forecast"][0]
    assert "upper" in result["forecast"][0]


def test_forecast_ensemble_no_combined_interval_when_component_missing_one():
    # A 2-row series is enough for naive's POINT forecast but not enough
    # to estimate its own residual variance, so it stays point-only --
    # the ensemble should then report no combined interval at all rather
    # than silently averaging over a missing bound.
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=2), "value": [100.0, 102.0]})
    result = forecast_ensemble(df, model_types=["naive", "naive"], horizon=5)
    assert "lower" not in result["forecast"][0]
    assert "No combined interval" in result["interval_note"]


def test_forecast_ensemble_combined_interval_when_all_components_have_one(sample_df):
    result = forecast_ensemble(sample_df, model_types=["ets", "sarima"], horizon=10)
    assert "lower" in result["forecast"][0]
    assert "upper" in result["forecast"][0]


def test_forecast_ensemble_interval_is_variance_combined_not_bound_averaged(sample_df):
    # Two identical naive components at equal weight (0.5 each): under the
    # independence assumption, combined sigma = sigma * sqrt(0.5^2+0.5^2)
    # = sigma / sqrt(2), i.e. NARROWER than either component's own
    # interval -- the opposite of what a plain bound average would give
    # (which would reproduce the single naive interval exactly, same as
    # the point forecast does in the weighted-average test above).
    single = forecast_naive(sample_df, horizon=5, method="naive")
    single_width = single["forecast"][0]["upper"] - single["forecast"][0]["lower"]

    ensemble = forecast_ensemble(sample_df, model_types=["naive", "naive"], horizon=5, model_params={"naive": {"method": "naive"}})
    combined_width = ensemble["forecast"][0]["upper"] - ensemble["forecast"][0]["lower"]

    assert combined_width == pytest.approx(single_width / (2**0.5), rel=1e-2)
    assert combined_width < single_width
    assert "independent" in ensemble["interval_note"].lower()


def test_forecast_ensemble_gbt_caveat_present(sample_df):
    result = forecast_ensemble(sample_df, model_types=["sarima", "gbt"], horizon=10)
    assert "caveat" in result
    assert "recursive" in result["caveat"].lower()


def test_forecast_ensemble_requires_at_least_two_models(sample_df):
    result = forecast_ensemble(sample_df, model_types=["sarima"], horizon=10)
    assert "error" in result


def test_forecast_ensemble_rejects_unknown_model_type(sample_df):
    result = forecast_ensemble(sample_df, model_types=["sarima", "not_a_model"], horizon=10)
    assert "error" in result


def test_forecast_ensemble_rejects_mismatched_weights(sample_df):
    result = forecast_ensemble(sample_df, model_types=["sarima", "ets"], horizon=10, weights=[1, 2, 3])
    assert "error" in result


def test_forecast_ensemble_rejects_negative_weights(sample_df):
    result = forecast_ensemble(sample_df, model_types=["sarima", "ets"], horizon=10, weights=[-1, 2])
    assert "error" in result
