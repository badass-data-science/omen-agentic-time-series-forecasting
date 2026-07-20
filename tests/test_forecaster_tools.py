import numpy as np
import pytest

pytest.importorskip("statsmodels")
pytest.importorskip("sklearn")

from omen.data_prep import generate_synthetic_series
from omen.forecaster.model_tools import (
    train_test_split,
    fit_naive_baselines,
    fit_ets,
    fit_sarima,
    fit_gradient_boosted_trees,
    compute_metrics_with_ci,
    residual_diagnostics,
    diebold_mariano_test,
    rolling_origin_backtest,
    search_sarima_orders,
)


@pytest.fixture
def sample_df():
    return generate_synthetic_series(n_days=300)


def test_train_test_split_sizes(sample_df):
    train, test = train_test_split(sample_df, holdout_size=30)
    assert len(train) == 270
    assert len(test) == 30


def test_fit_naive_baselines_seasonal_beats_flat_on_seasonal_data(sample_df):
    result = fit_naive_baselines(sample_df, holdout_size=30, seasonal_period=7)
    assert result["seasonal_naive"]["mae"] < result["naive"]["mae"]


def test_fit_naive_baselines_includes_holdout_arrays_and_ci(sample_df):
    result = fit_naive_baselines(sample_df, holdout_size=30, seasonal_period=7)
    assert len(result["holdout_actuals"]) == 30
    assert len(result["naive"]["holdout_predicted"]) == 30
    assert len(result["seasonal_naive"]["holdout_predicted"]) == 30
    assert result["seasonal_naive"]["mae_ci_lower"] <= result["seasonal_naive"]["mae"]
    assert result["seasonal_naive"]["mae"] <= result["seasonal_naive"]["mae_ci_upper"]


def test_fit_ets_returns_metrics_and_aic(sample_df):
    result = fit_ets(sample_df, holdout_size=30, seasonal_period=7)
    assert "aic" in result
    assert "mae" in result["backtest_metrics"]


def test_fit_ets_includes_holdout_arrays_and_ci(sample_df):
    result = fit_ets(sample_df, holdout_size=30, seasonal_period=7)
    assert len(result["holdout_actuals"]) == 30
    assert len(result["holdout_predicted"]) == 30
    metrics = result["backtest_metrics"]
    assert metrics["mae_ci_lower"] <= metrics["mae"] <= metrics["mae_ci_upper"]
    assert metrics["rmse_ci_lower"] <= metrics["rmse"] <= metrics["rmse_ci_upper"]


def test_fit_ets_reports_aicc_and_backtest_interval_coverage(sample_df):
    result = fit_ets(sample_df, holdout_size=30, seasonal_period=7)
    assert result["aicc"] is not None
    assert result["aicc"] >= result["aic"]  # AICc's correction term is always >= 0
    coverage = result["backtest_interval_coverage"]
    assert "error" not in coverage
    assert 0 <= coverage["empirical_coverage_pct"] <= 100
    assert coverage["nominal_confidence_pct"] == 95.0


def test_fit_sarima_returns_metrics_and_aic_bic(sample_df):
    result = fit_sarima(sample_df, holdout_size=30, order=[1, 1, 1], seasonal_order=[1, 1, 1, 7])
    assert "aic" in result and "bic" in result


def test_fit_sarima_includes_holdout_arrays_and_ljung_box_effect_size(sample_df):
    result = fit_sarima(sample_df, holdout_size=30, order=[1, 1, 1], seasonal_order=[1, 1, 1, 7])
    assert len(result["holdout_actuals"]) == 30
    assert len(result["holdout_predicted"]) == 30
    diag = result["residual_diagnostics"]
    assert "ljung_box_statistic" in diag
    assert "ljung_box_critical_value" in diag
    assert "ljung_box_effect_size" in diag
    assert diag["ljung_box_effect_size"] == pytest.approx(
        diag["ljung_box_statistic"] / diag["ljung_box_critical_value"], abs=1e-3
    )


def test_fit_sarima_reports_aicc_and_backtest_interval_coverage(sample_df):
    result = fit_sarima(sample_df, holdout_size=30, order=[1, 1, 1], seasonal_order=[1, 1, 1, 7])
    assert result["aicc"] is not None
    assert result["aicc"] >= result["aic"]
    coverage = result["backtest_interval_coverage"]
    assert "error" not in coverage
    assert 0 <= coverage["empirical_coverage_pct"] <= 100
    assert coverage["nominal_confidence_pct"] == 95.0


def test_fit_gradient_boosted_trees_flags_evaluation_caveat(sample_df):
    result = fit_gradient_boosted_trees(sample_df, holdout_size=30)
    assert "evaluation_caveat" in result
    assert "feature_importances" in result


def test_fit_gradient_boosted_trees_includes_holdout_arrays(sample_df):
    result = fit_gradient_boosted_trees(sample_df, holdout_size=30)
    assert len(result["holdout_actuals"]) == 30
    assert len(result["holdout_predicted"]) == 30


def test_compute_metrics_with_ci_brackets_point_estimate():
    rng = np.random.default_rng(0)
    y_true = rng.normal(100, 5, size=40)
    y_pred = y_true + rng.normal(0, 2, size=40)
    result = compute_metrics_with_ci(y_true, y_pred, seed=42)
    assert result["mae_ci_lower"] <= result["mae"] <= result["mae_ci_upper"]
    assert result["rmse_ci_lower"] <= result["rmse"] <= result["rmse_ci_upper"]
    assert result["mape_pct_ci_lower"] <= result["mape_pct"] <= result["mape_pct_ci_upper"]


def test_compute_metrics_with_ci_is_deterministic_given_the_same_seed():
    rng = np.random.default_rng(1)
    y_true = rng.normal(100, 5, size=40)
    y_pred = y_true + rng.normal(0, 2, size=40)
    result_a = compute_metrics_with_ci(y_true, y_pred, seed=7)
    result_b = compute_metrics_with_ci(y_true, y_pred, seed=7)
    assert result_a == result_b


def test_compute_metrics_with_ci_widens_with_higher_confidence_level():
    rng = np.random.default_rng(2)
    y_true = rng.normal(100, 5, size=40)
    y_pred = y_true + rng.normal(0, 2, size=40)
    narrow = compute_metrics_with_ci(y_true, y_pred, confidence_level=0.80, seed=42)
    wide = compute_metrics_with_ci(y_true, y_pred, confidence_level=0.99, seed=42)
    narrow_width = narrow["mae_ci_upper"] - narrow["mae_ci_lower"]
    wide_width = wide["mae_ci_upper"] - wide["mae_ci_lower"]
    assert wide_width > narrow_width


def test_residual_diagnostics_flags_autocorrelated_residuals_with_large_effect_size():
    rng = np.random.default_rng(3)
    n = 100
    residuals = np.zeros(n)
    for t in range(1, n):
        residuals[t] = 0.8 * residuals[t - 1] + rng.normal(0, 1.0)  # strongly autocorrelated

    result = residual_diagnostics(residuals, lags=10)
    assert result["residuals_look_like_white_noise"] is False
    assert result["ljung_box_effect_size"] > 1


def test_residual_diagnostics_passes_white_noise():
    rng = np.random.default_rng(4)
    residuals = rng.normal(0, 1.0, size=100)
    result = residual_diagnostics(residuals, lags=10)
    assert result["residuals_look_like_white_noise"] is True
    assert result["ljung_box_effect_size"] < 1


def test_diebold_mariano_test_favors_the_clearly_more_accurate_model():
    rng = np.random.default_rng(5)
    n = 40
    actuals = rng.normal(100, 5, size=n)
    predicted_a = actuals + rng.normal(0, 0.5, size=n)  # accurate
    predicted_b = actuals + rng.normal(0, 8.0, size=n)  # noisy

    result = diebold_mariano_test(actuals, predicted_a, predicted_b, model_a_name="Accurate", model_b_name="Noisy")
    assert result["is_significant_difference"] is True
    assert result["favored_model"] == "Accurate"
    assert result["p_value"] < 0.05


def test_diebold_mariano_test_finds_no_difference_for_near_identical_models():
    rng = np.random.default_rng(6)
    n = 40
    actuals = rng.normal(100, 5, size=n)
    predicted_a = actuals + rng.normal(0, 2.0, size=n)
    predicted_b = actuals + rng.normal(0, 2.0, size=n)

    result = diebold_mariano_test(actuals, predicted_a, predicted_b)
    assert result["is_significant_difference"] is False
    assert result["favored_model"] is None


def test_diebold_mariano_test_errors_on_mismatched_lengths():
    result = diebold_mariano_test([1, 2, 3], [1, 2], [1, 2, 3])
    assert "error" in result


def test_diebold_mariano_test_errors_on_invalid_loss():
    result = diebold_mariano_test([1, 2, 3, 4, 5, 6, 7, 8], [1, 2, 3, 4, 5, 6, 7, 8], [1, 2, 3, 4, 5, 6, 7, 9], loss="bogus")
    assert "error" in result


def test_diebold_mariano_test_errors_on_identical_predictions():
    actuals = list(range(20))
    predicted = [v + 1 for v in actuals]
    result = diebold_mariano_test(actuals, predicted, predicted)
    assert "error" in result


def test_diebold_mariano_test_n_lags_zero_is_respected():
    rng = np.random.default_rng(7)
    n = 40
    actuals = rng.normal(100, 5, size=n)
    predicted_a = actuals + rng.normal(0, 0.5, size=n)
    predicted_b = actuals + rng.normal(0, 8.0, size=n)
    result = diebold_mariano_test(actuals, predicted_a, predicted_b, n_lags=0)
    assert result["n_lags_used"] == 0


@pytest.fixture
def longer_sample_df():
    return generate_synthetic_series(n_days=400)


def test_rolling_origin_backtest_expanding_windows_are_chronological(longer_sample_df):
    result = rolling_origin_backtest(
        longer_sample_df,
        model_type="sarima",
        params={"order": [1, 1, 1], "seasonal_order": [1, 1, 1, 7]},
        holdout_size=30,
        n_origins=3,
    )
    assert result["n_origins_failed"] == 0
    origins = result["origins"]
    assert len(origins) == 3
    # Chronological order: origin 0 is the earliest, train_size grows.
    train_sizes = [o["train_size"] for o in origins]
    assert train_sizes == sorted(train_sizes)
    test_ranges = [o["test_range"][0] for o in origins]
    assert test_ranges == sorted(test_ranges)
    assert result["mae_mean"] is not None
    assert result["mae_std"] is not None


def test_rolling_origin_backtest_rejects_naive(longer_sample_df):
    result = rolling_origin_backtest(longer_sample_df, model_type="naive")
    assert "error" in result


def test_rolling_origin_backtest_rejects_unknown_model_type(longer_sample_df):
    result = rolling_origin_backtest(longer_sample_df, model_type="prophet")
    assert "error" in result


def test_rolling_origin_backtest_errors_on_insufficient_data(longer_sample_df):
    result = rolling_origin_backtest(longer_sample_df, model_type="sarima", holdout_size=100, n_origins=10)
    assert "error" in result


def test_rolling_origin_backtest_works_for_ets_and_gbt(longer_sample_df):
    ets_result = rolling_origin_backtest(
        longer_sample_df, model_type="ets", params={"seasonal_period": 7}, holdout_size=30, n_origins=2
    )
    assert ets_result["n_origins_failed"] == 0
    assert len(ets_result["origins"]) == 2

    gbt_result = rolling_origin_backtest(longer_sample_df, model_type="gbt", holdout_size=30, n_origins=2)
    assert gbt_result["n_origins_failed"] == 0
    assert len(gbt_result["origins"]) == 2


def test_search_sarima_orders_returns_ranked_candidates(sample_df):
    result = search_sarima_orders(
        sample_df, holdout_size=30, seasonal_period=7, max_p=1, max_q=1, max_seasonal_p=1, max_seasonal_q=1
    )
    assert result["n_combinations_tried"] == 16
    candidates = result["top_candidates"]
    assert len(candidates) > 0
    rank_keys = [c["aicc"] if c["aicc"] is not None else c["aic"] for c in candidates]
    assert rank_keys == sorted(rank_keys)
    for c in candidates:
        assert "order" in c and "seasonal_order" in c
        assert "backtest_metrics" in c
        assert "residuals_look_like_white_noise" in c


def test_search_sarima_orders_respects_max_combinations(sample_df):
    result = search_sarima_orders(
        sample_df, max_p=2, max_q=2, max_seasonal_p=1, max_seasonal_q=1, max_combinations=30
    )
    assert "error" in result


def test_search_sarima_orders_holds_d_and_seasonal_d_fixed(sample_df):
    result = search_sarima_orders(
        sample_df, seasonal_period=7, d=1, seasonal_d=0, max_p=1, max_q=0, max_seasonal_p=1, max_seasonal_q=0
    )
    for c in result["top_candidates"]:
        assert c["order"][1] == 1
        assert c["seasonal_order"][1] == 0
