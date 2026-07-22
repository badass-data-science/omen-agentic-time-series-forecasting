import pytest

pytest.importorskip("statsmodels")

from omen.data_prep import generate_synthetic_series
from omen.analyst.plot_tools import (
    plot_series,
    plot_acf_pacf,
    plot_seasonal_decomposition,
    plot_periodogram,
    plot_anomalies,
    plot_changepoints,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def sample_df():
    return generate_synthetic_series(n_days=200)


def _assert_valid_png_result(result, expected_status_keys=()):
    image_content = result.content[0]
    assert image_content.type == "image"
    assert image_content.mimeType == "image/png"
    import base64

    raw = base64.b64decode(image_content.data)
    assert raw.startswith(PNG_MAGIC)
    assert len(raw) > 100  # a real rendered figure, not an empty/degenerate image
    assert result.structured_content["status"] == "ok"
    for key in expected_status_keys:
        assert key in result.structured_content


def test_plot_series_returns_valid_png(sample_df):
    result = plot_series(sample_df)
    _assert_valid_png_result(result, expected_status_keys=("n_observations", "n_missing"))
    assert result.structured_content["n_observations"] == 200
    assert result.structured_content["written_to"] is None


def test_plot_series_writes_out_path(sample_df, tmp_path):
    out_path = str(tmp_path / "series.png")
    result = plot_series(sample_df, out_path=out_path)
    assert result.structured_content["written_to"] == out_path
    with open(out_path, "rb") as f:
        assert f.read().startswith(PNG_MAGIC)


def test_plot_acf_pacf_returns_valid_png(sample_df):
    result = plot_acf_pacf(sample_df, n_lags=14)
    _assert_valid_png_result(result, expected_status_keys=("n_lags",))
    assert result.structured_content["n_lags"] == 14


def test_plot_seasonal_decomposition_returns_valid_png(sample_df):
    result = plot_seasonal_decomposition(sample_df, period=7)
    _assert_valid_png_result(result, expected_status_keys=("period_assumed",))
    assert result.structured_content["period_assumed"] == 7


def test_plot_seasonal_decomposition_raises_on_too_short_series():
    df = generate_synthetic_series(n_days=5)
    with pytest.raises(ValueError):
        plot_seasonal_decomposition(df, period=7)


def test_plot_periodogram_returns_valid_png(sample_df):
    result = plot_periodogram(sample_df)
    _assert_valid_png_result(
        result, expected_status_keys=("dominant_period", "dominant_period_in_reported_range")
    )


def test_plot_anomalies_marks_a_real_injected_spike(sample_df):
    df = sample_df.copy()
    df.loc[100, "value"] += 500.0  # obvious, real anomaly
    result = plot_anomalies(df)
    _assert_valid_png_result(result, expected_status_keys=("n_anomalies_flagged",))
    assert result.structured_content["n_anomalies_flagged"] >= 1


def test_plot_anomalies_flags_nothing_on_a_clean_series(sample_df):
    result = plot_anomalies(sample_df)
    _assert_valid_png_result(result)
    assert result.structured_content["n_anomalies_flagged"] == 0


def test_plot_changepoints_returns_valid_png(sample_df):
    result = plot_changepoints(sample_df)
    _assert_valid_png_result(result, expected_status_keys=("n_changepoints_found",))


def test_plot_changepoints_raises_on_too_short_series():
    df = generate_synthetic_series(n_days=5)
    with pytest.raises(ValueError):
        plot_changepoints(df, min_segment_size=10)
