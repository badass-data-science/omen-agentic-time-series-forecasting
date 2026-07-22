import base64

from omen.data_prep import generate_synthetic_series
from omen.monitor.monitor_tools import detect_data_drift, rolling_drift_check
from omen.monitor.plot_tools import plot_forecast_vs_actuals, plot_drift, plot_rolling_drift


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _assert_valid_png_result(result, out_path=None, expected_status="ok"):
    assert result.content
    image_content = result.content[0]
    assert image_content.type == "image"
    assert image_content.mimeType == "image/png"
    raw = base64.b64decode(image_content.data)
    assert raw.startswith(PNG_MAGIC)
    assert result.structured_content["status"] == expected_status
    if out_path is not None:
        assert result.structured_content["written_to"] == out_path
        with open(out_path, "rb") as f:
            assert f.read().startswith(PNG_MAGIC)


def test_plot_forecast_vs_actuals_real_matched_points(tmp_path):
    df = generate_synthetic_series(n_days=100)
    last_10 = df.iloc[-10:].reset_index(drop=True)
    forecast = [{"note": "irrelevant truncation marker"}] + [
        {
            "date": str(row["date"].date()),
            "forecast": float(row["value"]) * 0.95,
            "lower": float(row["value"]) * 0.8,
            "upper": float(row["value"]) * 1.1,
        }
        for _, row in last_10.iterrows()
    ]

    out_path = str(tmp_path / "fva.png")
    result = plot_forecast_vs_actuals(forecast, df, out_path=out_path)
    _assert_valid_png_result(result, out_path=out_path)
    assert result.structured_content["n_dates_compared"] == 10
    assert result.structured_content["has_interval"] is True


def test_plot_forecast_vs_actuals_no_overlap_reports_error_plot():
    df = generate_synthetic_series(n_days=50)
    forecast = [{"date": "2099-01-01", "forecast": 100.0}]
    result = plot_forecast_vs_actuals(forecast, df)
    _assert_valid_png_result(result, expected_status="error")


def test_plot_drift_flags_trending_series():
    df = generate_synthetic_series()  # default params include a real trend
    real = detect_data_drift(df)
    result = plot_drift(df)
    _assert_valid_png_result(result)
    assert result.structured_content["drift_detected"] == real["drift_detected"]
    assert result.structured_content["mean_shift_cohens_d"] == real["mean_shift_cohens_d"]


def test_plot_rolling_drift_real_checks(tmp_path):
    df = generate_synthetic_series()
    real = rolling_drift_check(df, n_checks=5)
    out_path = str(tmp_path / "rolling.png")
    result = plot_rolling_drift(real["checks"], out_path=out_path)
    _assert_valid_png_result(result, out_path=out_path)
    assert result.structured_content["n_checks_plotted"] == 5
    assert result.structured_content["n_flagged"] == real["n_flagged"]
