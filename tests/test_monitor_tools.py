from omen.data_prep import generate_synthetic_series
from omen.monitor.monitor_tools import (
    compute_metrics,
    compare_forecast_to_actuals,
    detect_data_drift,
    recommend_retraining,
)


def test_compute_metrics_basic():
    metrics = compute_metrics([10, 20, 30], [11, 19, 30])
    assert metrics["mae"] > 0
    assert metrics["mape_pct"] is not None


def test_detect_data_drift_flags_injected_mean_shift():
    df = generate_synthetic_series(n_days=200)
    df.loc[df.index[-30:], "value"] += 200  # inject an obvious level shift
    result = detect_data_drift(df, recent_window_size=30, reference_window_size=90)
    assert result["drift_detected"] is True


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


def test_compare_forecast_to_actuals_returns_error_when_no_dates_match():
    df = generate_synthetic_series(n_days=30)
    result = compare_forecast_to_actuals([{"date": "2099-01-01", "forecast": 1.0}], df)
    assert "error" in result


def test_recommend_retraining_decision_matrix():
    assert recommend_retraining(mape_now=25, mape_backtest=10, drift_detected=True)["recommendation"] == "retrain_now"
    assert recommend_retraining(mape_now=25, mape_backtest=10, drift_detected=False)["recommendation"] == "investigate"
    assert recommend_retraining(mape_now=10.5, mape_backtest=10, drift_detected=True)["recommendation"] == "monitor_closely"
    assert recommend_retraining(mape_now=10.5, mape_backtest=10, drift_detected=False)["recommendation"] == "no_action_needed"
