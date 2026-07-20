"""
server.py — FastMCP server for the Layer 3 deployment forecast tools.

Retrains a chosen model on the FULL series (informed by Layer 2's backtest
results, but doesn't repeat that backtest itself) and produces a genuine
forecast for dates beyond the last observation, with prediction intervals
where the model supports them.

Run over stdio (how OpenClaw will launch it), after `pip install -e .`:
    ts-deploy-server
    # or: python -m omen.deploy.server
"""

from typing import Optional

from fastmcp import FastMCP

from omen.data_prep import load_series
from .forecast_tools import (
    forecast_naive as _forecast_naive,
    forecast_ets as _forecast_ets,
    forecast_sarima as _forecast_sarima,
    forecast_gradient_boosted_trees as _forecast_gradient_boosted_trees,
)

mcp = FastMCP("ts-deploy")


@mcp.tool()
def forecast_naive(
    csv_path: str,
    horizon: int = 30,
    seasonal_period: int = 7,
    method: str = "seasonal_naive",
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Extend the series with a trivial baseline forecast beyond the last
    observed date -- either flat ("naive": repeat the last value) or
    seasonal ("seasonal_naive": repeat the last full seasonal cycle). No
    prediction interval; useful as a sanity-check floor alongside a real
    model's forecast.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        horizon: Number of future steps to forecast.
        seasonal_period: Seasonal cycle length, used only if method is seasonal_naive.
        method: "seasonal_naive" or "naive".
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _forecast_naive(df, horizon=horizon, seasonal_period=seasonal_period, method=method)


@mcp.tool()
def forecast_ets(
    csv_path: str,
    horizon: int = 30,
    seasonal_period: int = 7,
    trend: str = "add",
    seasonal: str = "add",
    damped_trend: bool = False,
    confidence_level: float = 0.95,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Retrain Holt-Winters (ETS) on the FULL series and forecast `horizon`
    steps beyond the last observation. Returns a prediction interval
    derived from simulated future paths (falls back to point-forecast-only
    if simulation isn't supported for this parameter combination).

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        horizon: Number of future steps to forecast.
        seasonal_period: Seasonal cycle length (e.g. 7 for weekly in daily data).
        trend: "add", "mul", or None.
        seasonal: "add", "mul", or None.
        damped_trend: Whether to damp the trend component.
        confidence_level: Width of the prediction interval, e.g. 0.95 for 95%.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _forecast_ets(
        df,
        horizon=horizon,
        seasonal_period=seasonal_period,
        trend=trend,
        seasonal=seasonal,
        damped_trend=damped_trend,
        confidence_level=confidence_level,
    )


@mcp.tool()
def forecast_sarima(
    csv_path: str,
    horizon: int = 30,
    order: Optional[list] = None,
    seasonal_order: Optional[list] = None,
    confidence_level: float = 0.95,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Retrain SARIMA on the FULL series and forecast `horizon` steps
    beyond the last observation, with an analytic confidence interval from
    the state-space model.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        horizon: Number of future steps to forecast.
        order: [p, d, q] non-seasonal ARIMA order. Defaults to [1, 1, 1].
        seasonal_order: [P, D, Q, s] seasonal order. Defaults to [1, 1, 1, 7].
        confidence_level: Width of the confidence interval, e.g. 0.95 for 95%.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _forecast_sarima(
        df, horizon=horizon, order=order, seasonal_order=seasonal_order, confidence_level=confidence_level
    )


@mcp.tool()
def forecast_gradient_boosted_trees(
    csv_path: str,
    horizon: int = 30,
    lags: Optional[list] = None,
    n_estimators: int = 200,
    max_depth: int = 3,
    learning_rate: float = 0.05,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Retrain gradient-boosted trees on lag + calendar features using the
    FULL series, then forecast `horizon` steps ahead RECURSIVELY -- each
    predicted value feeds back in as a lag feature for later steps. No
    native prediction interval. This compounding-error risk is real and
    grows with horizon length; the tool result flags it explicitly.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        horizon: Number of future steps to forecast.
        lags: List of lag steps to use as features. Defaults to [1, 7, 14].
        n_estimators: Number of boosting stages.
        max_depth: Max depth per tree.
        learning_rate: Shrinkage rate applied to each tree's contribution.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _forecast_gradient_boosted_trees(
        df, horizon=horizon, lags=lags, n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate
    )


def main():
    """Entry point for the `ts-deploy-server` console script."""
    mcp.run()  # defaults to stdio transport, which is what OpenClaw expects


if __name__ == "__main__":
    main()
