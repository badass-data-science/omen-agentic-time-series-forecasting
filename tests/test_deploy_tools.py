import pytest

pytest.importorskip("statsmodels")
pytest.importorskip("sklearn")

from omen.data_prep import generate_synthetic_series
from omen.deploy.forecast_tools import (
    forecast_naive,
    forecast_ets,
    forecast_sarima,
    forecast_gradient_boosted_trees,
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


def test_forecast_ets_has_interval_note(sample_df):
    result = forecast_ets(sample_df, horizon=10)
    assert "interval_note" in result


def test_forecast_sarima_has_analytic_interval(sample_df):
    result = forecast_sarima(sample_df, horizon=10)
    assert "lower" in result["forecast"][0]
    assert "upper" in result["forecast"][0]


def test_forecast_gbt_flags_compounding_error_caveat(sample_df):
    result = forecast_gradient_boosted_trees(sample_df, horizon=10)
    assert "caveat" in result
    assert "recursive" in result["caveat"].lower() or "compound" in result["caveat"].lower()
