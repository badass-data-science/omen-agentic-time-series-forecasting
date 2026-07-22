import pytest

pytest.importorskip("statsmodels")

from omen.data_prep import generate_synthetic_series
from omen.deploy.forecast_tools import forecast_ets
from omen.deploy.plot_tools import plot_forecast


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def sample_df():
    return generate_synthetic_series(n_days=300)


def _assert_valid_png_result(result, out_path=None):
    assert result.content
    image_content = result.content[0]
    assert image_content.type == "image"
    assert image_content.mimeType == "image/png"
    import base64

    raw = base64.b64decode(image_content.data)
    assert raw.startswith(PNG_MAGIC)
    assert result.structured_content["status"] == "ok"
    if out_path is not None:
        assert result.structured_content["written_to"] == out_path
        with open(out_path, "rb") as f:
            assert f.read().startswith(PNG_MAGIC)


def test_plot_forecast_real_forecast(sample_df, tmp_path):
    forecast_result = forecast_ets(sample_df, horizon=14)
    out_path = str(tmp_path / "forecast.png")
    result = plot_forecast(sample_df, forecast_result["forecast"], out_path=out_path)
    _assert_valid_png_result(result, out_path=out_path)
    assert result.structured_content["n_forecast_points_plotted"] == 14
    assert result.structured_content["has_interval"] is True


def test_plot_forecast_inline_only_no_out_path(sample_df):
    forecast_result = forecast_ets(sample_df, horizon=5)
    result = plot_forecast(sample_df, forecast_result["forecast"])
    _assert_valid_png_result(result, out_path=None)
    assert result.structured_content["written_to"] is None


def test_plot_forecast_handles_truncated_long_horizon(sample_df):
    forecast_result = forecast_ets(sample_df, horizon=90)  # triggers _format_forecast's cap=60 truncation
    assert any("note" in p for p in forecast_result["forecast"])
    result = plot_forecast(sample_df, forecast_result["forecast"])
    _assert_valid_png_result(result)
    assert result.structured_content["n_forecast_points_omitted"] > 0
