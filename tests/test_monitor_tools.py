from omen.data_prep import generate_synthetic_series
from omen.monitor.monitor_tools import (
    compute_metrics,
    compute_metrics_with_ci,
    compare_forecast_to_actuals,
    detect_data_drift,
    rolling_drift_check,
    recommend_retraining,
)


def test_compute_metrics_basic():
    metrics = compute_metrics([10, 20, 30], [11, 19, 30])
    assert metrics["mae"] > 0
    assert metrics["mape_pct"] is not None


def test_compute_metrics_with_ci_includes_bootstrap_bounds():
    metrics = compute_metrics_with_ci([10, 20, 30, 40, 50], [11, 19, 30, 42, 48], n_bootstrap=200, seed=1)
    assert metrics["mae"] > 0  # pre-existing fields unchanged
    assert metrics["mae_ci_lower"] <= metrics["mae"] <= metrics["mae_ci_upper"]
    assert metrics["rmse_ci_lower"] <= metrics["rmse"] <= metrics["rmse_ci_upper"]
    assert metrics["ci_n_bootstrap"] == 200


def test_detect_data_drift_flags_injected_mean_shift():
    df = generate_synthetic_series(n_days=200)
    df.loc[df.index[-30:], "value"] += 200  # inject an obvious level shift
    result = detect_data_drift(df, recent_window_size=30, reference_window_size=90)
    assert result["drift_detected"] is True


def test_detect_data_drift_reports_effect_size_and_raw_statistics():
    df = generate_synthetic_series(n_days=200)
    df.loc[df.index[-30:], "value"] += 200  # large, obvious level shift
    result = detect_data_drift(df, recent_window_size=30, reference_window_size=90)
    assert result["mean_shift_cohens_d"] is not None
    assert abs(result["mean_shift_cohens_d"]) > 1  # a +200 shift should be a large effect
    assert "ttest_statistic" in result
    assert "ks_statistic" in result
    assert 0 <= result["ks_statistic"] <= 1
    assert "Cohen's d" in result["interpretation"]


def test_detect_data_drift_effect_size_is_much_larger_with_an_injected_shift():
    # The project's own synthetic data has a real upward trend, so even the
    # unmodified series can show a nonzero (and even "significant") mean
    # shift between windows -- see AGENTS.md's documented false-positive
    # caveat. Rather than assert an arbitrary fixed bound on either case,
    # compare them relatively: injecting an obvious +200 level shift should
    # produce a MUCH larger effect size than the trend-only baseline.
    baseline_df = generate_synthetic_series(n_days=200)
    baseline = detect_data_drift(baseline_df, recent_window_size=30, reference_window_size=90)

    shifted_df = generate_synthetic_series(n_days=200)
    shifted_df.loc[shifted_df.index[-30:], "value"] += 200
    shifted = detect_data_drift(shifted_df, recent_window_size=30, reference_window_size=90)

    assert abs(shifted["mean_shift_cohens_d"]) > abs(baseline["mean_shift_cohens_d"]) * 2


def test_detect_data_drift_errors_on_too_little_data():
    df = generate_synthetic_series(n_days=10)
    result = detect_data_drift(df, recent_window_size=30, reference_window_size=90)
    assert "error" in result


def test_compare_forecast_to_actuals_matches_and_skips_truncation_notes():
    df = generate_synthetic_series(n_days=100)
    last_5 = df.iloc[-5:].reset_index(drop=True)

    forecast = [{"note": "irrelevant truncation marker"}]
    for _, row in last_5.iterrows():
        forecast.append(
            {
                "date": str(row["date"].date()),
                "forecast": float(row["value"]) * 0.95,
                "lower": float(row["value"]) * 0.8,
                "upper": float(row["value"]) * 1.1,
            }
        )

    result = compare_forecast_to_actuals(forecast, df)
    assert result["n_dates_compared"] == 5
    assert result["interval_coverage"]["interval_available"] is True


def test_compare_forecast_to_actuals_includes_bootstrap_ci_on_metrics():
    df = generate_synthetic_series(n_days=100)
    last_10 = df.iloc[-10:].reset_index(drop=True)

    forecast = [
        {"date": str(row["date"].date()), "forecast": float(row["value"]) * 0.95}
        for _, row in last_10.iterrows()
    ]

    result = compare_forecast_to_actuals(forecast, df, n_bootstrap=200, seed=1)
    metrics = result["backtest_style_metrics"]
    assert metrics["mae_ci_lower"] <= metrics["mae"] <= metrics["mae_ci_upper"]
    assert metrics["ci_n_bootstrap"] == 200


def test_compare_forecast_to_actuals_wilson_ci_on_coverage():
    df = generate_synthetic_series(n_days=100)
    last_5 = df.iloc[-5:].reset_index(drop=True)

    forecast = [
        {
            "date": str(row["date"].date()),
            "forecast": float(row["value"]) * 0.95,
            "lower": float(row["value"]) * 0.8,
            "upper": float(row["value"]) * 1.1,
        }
        for _, row in last_5.iterrows()
    ]

    result = compare_forecast_to_actuals(forecast, df)
    coverage = result["interval_coverage"]
    assert coverage["empirical_coverage_ci_lower"] <= coverage["empirical_coverage_pct"] <= coverage["empirical_coverage_ci_upper"]
    assert "Wilson score" in coverage["interpretation"]
    # well_calibrated's existing threshold logic must be untouched by the new CI fields
    assert coverage["well_calibrated"] == (abs(coverage["empirical_coverage_pct"] - coverage["nominal_confidence_pct"]) <= 15)


def test_compare_forecast_to_actuals_flags_residual_outlier():
    df = generate_synthetic_series(n_days=100)
    last_10 = df.iloc[-10:].reset_index(drop=True)

    forecast = []
    for i, row in last_10.iterrows():
        # Every day forecasts within a small, non-degenerate miss except one
        # wild one -- NOT an exact match for the other nine (that would make
        # every "good" residual exactly 0, degenerating the MAD to 0 too and
        # masking the outlier, the same self-dilution class of issue
        # ts-analyst's robust anomaly detector was built to avoid).
        forecast_value = float(row["value"]) * 0.01 if i == last_10.index[5] else float(row["value"]) * 0.99
        forecast.append({"date": str(row["date"].date()), "forecast": forecast_value})

    result = compare_forecast_to_actuals(forecast, df)
    outliers = result["residual_outliers"]
    assert len(outliers["flagged_dates"]) >= 1
    assert outliers["metrics_excluding_outliers"] is not None
    # Excluding the one wild miss should give a much lower MAPE than the full set.
    assert outliers["metrics_excluding_outliers"]["mape_pct"] < result["backtest_style_metrics"]["mape_pct"]


def test_compare_forecast_to_actuals_no_outliers_when_uniformly_off():
    df = generate_synthetic_series(n_days=100)
    last_10 = df.iloc[-10:].reset_index(drop=True)

    forecast = [
        {"date": str(row["date"].date()), "forecast": float(row["value"]) * 0.95}
        for _, row in last_10.iterrows()
    ]

    result = compare_forecast_to_actuals(forecast, df)
    assert result["residual_outliers"]["flagged_dates"] == []
    assert result["residual_outliers"]["metrics_excluding_outliers"] is None


def test_compare_forecast_to_actuals_returns_error_when_no_dates_match():
    df = generate_synthetic_series(n_days=30)
    result = compare_forecast_to_actuals([{"date": "2099-01-01", "forecast": 1.0}], df)
    assert "error" in result


def test_rolling_drift_check_persistent_on_trending_series():
    df = generate_synthetic_series(n_days=300)
    result = rolling_drift_check(df, recent_window_size=30, reference_window_size=90, n_checks=5)
    assert result["n_checks_failed"] == 0
    assert len(result["checks"]) == 5
    # Checks should read chronologically (oldest first).
    dates = [c["recent_window_end_date"] for c in result["checks"]]
    assert dates == sorted(dates)
    assert result["persistent_drift"] is True  # the project's own trend flags consistently


def test_rolling_drift_check_errors_on_insufficient_data():
    df = generate_synthetic_series(n_days=50)
    result = rolling_drift_check(df, recent_window_size=30, reference_window_size=90, n_checks=5)
    assert "error" in result


def test_rolling_drift_check_respects_persistence_threshold():
    df = generate_synthetic_series(n_days=300)
    lenient = rolling_drift_check(df, recent_window_size=30, reference_window_size=90, n_checks=5, persistence_threshold_frac=0.99)
    strict_but_still_reasonable = rolling_drift_check(
        df, recent_window_size=30, reference_window_size=90, n_checks=5, persistence_threshold_frac=0.1
    )
    assert lenient["frac_flagged"] == strict_but_still_reasonable["frac_flagged"]  # same underlying checks
    assert strict_but_still_reasonable["persistent_drift"] is True
    # A near-100% bar should be harder to clear than a near-0% one for the same data.
    assert lenient["persistent_drift"] is False or lenient["frac_flagged"] >= 0.99


def test_recommend_retraining_decision_matrix():
    assert recommend_retraining(mape_now=25, mape_backtest=10, drift_detected=True)["recommendation"] == "retrain_now"
    assert recommend_retraining(mape_now=25, mape_backtest=10, drift_detected=False)["recommendation"] == "investigate"
    assert recommend_retraining(mape_now=10.5, mape_backtest=10, drift_detected=True)["recommendation"] == "monitor_closely"
    assert recommend_retraining(mape_now=10.5, mape_backtest=10, drift_detected=False)["recommendation"] == "no_action_needed"


def test_recommend_retraining_reports_degradation_ci_when_supplied():
    result = recommend_retraining(
        mape_now=15, mape_backtest=10, drift_detected=False, mape_now_ci_lower=12, mape_now_ci_upper=18,
    )
    assert result["pct_degradation_ci_lower"] == 20.0  # 100*(12-10)/10
    assert result["pct_degradation_ci_upper"] == 80.0  # 100*(18-10)/10


def test_recommend_retraining_flags_threshold_within_ci():
    # Default error_degradation_threshold_pct is 20%. Point estimate (15%
    # implied degradation) says "not degraded," but the CI ([5%, 35%])
    # straddles the 20% threshold -- the verdict should be flagged as
    # sensitive to sampling noise rather than presented as clear-cut.
    result = recommend_retraining(
        mape_now=11.5, mape_backtest=10, drift_detected=False, mape_now_ci_lower=10.5, mape_now_ci_upper=13.5,
    )
    assert result["degradation_threshold_within_ci"] is True
    assert "sensitive to sampling noise" in result["reasoning"]


def test_recommend_retraining_omits_ci_fields_when_not_supplied():
    result = recommend_retraining(mape_now=25, mape_backtest=10, drift_detected=True)
    assert result["pct_degradation_ci_lower"] is None
    assert result["pct_degradation_ci_upper"] is None
    assert result["degradation_threshold_within_ci"] is None
