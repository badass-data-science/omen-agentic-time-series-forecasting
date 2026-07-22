import pytest

pytest.importorskip("statsmodels")
pytest.importorskip("sklearn")

from fastmcp.tools.tool import ToolResult

from omen.data_prep import generate_synthetic_series
from omen.forecaster.model_tools import fit_ets, rolling_origin_backtest, search_sarima_orders
from omen.forecaster.plot_tools import plot_backtest, plot_rolling_origin, plot_search_sarima_orders


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _assert_valid_png_result(result, expect_written_file=None):
    assert isinstance(result, ToolResult)
    assert len(result.content) == 1
    image_content = result.content[0]
    assert image_content.type == "image"
    assert image_content.mimeType == "image/png"
    import base64
    raw = base64.b64decode(image_content.data)
    assert raw[:8] == PNG_MAGIC
    assert result.structured_content["status"] == "ok"
    if expect_written_file:
        with open(expect_written_file, "rb") as f:
            assert f.read(8) == PNG_MAGIC


@pytest.fixture
def sample_df():
    return generate_synthetic_series(n_days=300)


def test_plot_backtest_no_interval(sample_df):
    fit = fit_ets(sample_df, holdout_size=30)
    result = plot_backtest(fit["holdout_actuals"], fit["holdout_predicted"], model_name="ETS")
    _assert_valid_png_result(result)
    assert result.structured_content["interval_shown"] is False
    assert result.structured_content["n_points_plotted"] == 30


def test_plot_backtest_with_interval_and_out_path(sample_df, tmp_path):
    fit = fit_ets(sample_df, holdout_size=30)
    lower = [v - 5 for v in fit["holdout_predicted"]]
    upper = [v + 5 for v in fit["holdout_predicted"]]
    out_path = str(tmp_path / "backtest.png")
    result = plot_backtest(
        fit["holdout_actuals"], fit["holdout_predicted"], model_name="ETS",
        lower=lower, upper=upper, out_path=out_path,
    )
    _assert_valid_png_result(result, expect_written_file=out_path)
    assert result.structured_content["interval_shown"] is True
    assert result.structured_content["written_to"] == out_path


def test_plot_rolling_origin_real_data(sample_df):
    # Real rolling_origin_backtest call -- catches any field-name mismatch
    # between what the tool actually returns and what the plot expects.
    rob = rolling_origin_backtest(sample_df, model_type="ets", holdout_size=30, n_origins=3, n_bootstrap=20)
    assert "error" not in rob
    result = plot_rolling_origin(rob["origins"])
    _assert_valid_png_result(result)
    assert result.structured_content["n_origins_plotted"] == 3
    assert result.structured_content["mape_pct_mean"] == pytest.approx(rob["mape_pct_mean"], rel=1e-6)


def test_plot_rolling_origin_skips_failed_origins():
    origins = [
        {"origin_index": 0, "error": "Fit failed at this origin: boom"},
        {"origin_index": 1, "train_size": 100, "test_range": ["2024-01-01", "2024-01-30"], "mae": 1.0, "rmse": 1.2, "mape_pct": 5.0},
        {"origin_index": 2, "train_size": 130, "test_range": ["2024-02-01", "2024-03-01"], "mae": 1.1, "rmse": 1.3, "mape_pct": 7.0},
    ]
    result = plot_rolling_origin(origins)
    _assert_valid_png_result(result)
    assert result.structured_content["n_origins_plotted"] == 2


def test_plot_rolling_origin_raises_on_all_failed():
    with pytest.raises(ValueError):
        plot_rolling_origin([{"origin_index": 0, "error": "boom"}])


def test_plot_search_sarima_orders_real_data(sample_df):
    search = search_sarima_orders(sample_df, holdout_size=30, d=1, seasonal_d=1, max_p=1, max_q=1, max_seasonal_p=0, max_seasonal_q=0, n_bootstrap_per_candidate=20)
    assert "error" not in search
    out_path_result = plot_search_sarima_orders(search["top_candidates"])
    _assert_valid_png_result(out_path_result)
    assert out_path_result.structured_content["n_candidates_plotted"] == len(search["top_candidates"])
    assert out_path_result.structured_content["best_order"] is not None


def test_plot_search_sarima_orders_raises_on_empty():
    with pytest.raises(ValueError):
        plot_search_sarima_orders([])
