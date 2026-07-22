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
from fastmcp.tools.tool import ToolResult

from fastmcp import FastMCP

from omen.data_prep import load_series
from .forecast_tools import (
    forecast_naive as _forecast_naive,
    forecast_ets as _forecast_ets,
    forecast_sarima as _forecast_sarima,
    forecast_gradient_boosted_trees as _forecast_gradient_boosted_trees,
    forecast_ensemble as _forecast_ensemble,
)
from .plot_tools import plot_forecast as _plot_forecast

mcp = FastMCP("ts-deploy")


@mcp.tool()
def forecast_naive(
    csv_path: str,
    horizon: int = 30,
    seasonal_period: int = 7,
    method: str = "seasonal_naive",
    confidence_level: float = 0.95,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Extend the series with a trivial baseline forecast beyond the last
    observed date -- either flat ("naive": repeat the last value) or
    seasonal ("seasonal_naive": repeat the last full seasonal cycle).
    Useful as a sanity-check floor alongside a real model's forecast.

    Includes an analytic prediction interval built from this same naive
    method's own in-sample residual standard deviation (one-step
    differences for flat naive, seasonal differences for seasonal naive),
    widening with the horizon -- the standard textbook interval for a
    random-walk-style forecast (Hyndman & Athanasopoulos), not
    simulation-based. Falls back to point-forecast-only (see
    `interval_note`) if there's not enough history to estimate a residual
    standard deviation.

    Also returns `plausibility_check`: compares this forecast's implied
    endpoint change against the empirical distribution of horizon-length
    changes the series has actually made historically, flagging
    `is_extreme_relative_to_history` and whether the forecast ever leaves
    the historical min/max range. Not a hypothesis test -- a prompt for
    scrutiny, not a verdict.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        horizon: Number of future steps to forecast.
        seasonal_period: Seasonal cycle length, used only if method is seasonal_naive.
        method: "seasonal_naive" or "naive".
        confidence_level: Width of the prediction interval, e.g. 0.95 for 95%.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _forecast_naive(df, horizon=horizon, seasonal_period=seasonal_period, method=method, confidence_level=confidence_level)


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

    Also returns `aic` and `aicc` (small-sample-corrected AIC, Hurvich &
    Tsai 1989 -- `null` when the training size is too small relative to
    the parameter count) for this refit on the FULL series, and
    `plausibility_check`: compares the forecast's implied endpoint change
    against the empirical distribution of horizon-length changes the
    series has actually made historically, flagging
    `is_extreme_relative_to_history` and whether the forecast ever leaves
    the historical min/max range. Note `aicc` here is NOT directly
    comparable to ts-forecaster's `fit_ets` `aicc` for the same series --
    that one is computed on the training split only, this one on the full
    series, so both `n` and the fitted params can differ.

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

    Also returns `aic`, `bic`, and `aicc` (small-sample-corrected AIC,
    Hurvich & Tsai 1989 -- `null` when the training size is too small
    relative to the parameter count) for this refit on the FULL series,
    and `plausibility_check`: compares the forecast's implied endpoint
    change against the empirical distribution of horizon-length changes
    the series has actually made historically, flagging
    `is_extreme_relative_to_history` and whether the forecast ever leaves
    the historical min/max range. Note `aicc` here is NOT directly
    comparable to ts-forecaster's `fit_sarima` `aicc` for the same series
    -- that one is computed on the training split only, this one on the
    full series, so both `n` and the fitted params can differ.

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
    confidence_level: float = 0.95,
    n_bootstrap: int = 100,
    seed: int = 42,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Retrain gradient-boosted trees on lag + calendar features using the
    FULL series, then forecast `horizon` steps ahead RECURSIVELY -- each
    predicted value feeds back in as a lag feature for later steps. This
    compounding-error risk is real and grows with horizon length; the
    tool result flags it explicitly in `caveat`.

    A prediction interval IS available here (unlike before): two extra
    quantile-regression models are fit alongside the point model. It's
    approximate -- see `interval_note` and `caveat` -- since it doesn't
    itself grow with the recursive compounding risk the way a proper
    multi-step interval would.

    `feature_importances` is `{col: {importance, ci_lower, ci_upper}}` --
    the CI comes from refitting on `n_bootstrap` resamples of the training
    rows, which is real extra compute (n_bootstrap extra full model fits
    on top of the three already needed for the forecast+interval). Pass
    `n_bootstrap=0` to skip this and get `ci_lower`/`ci_upper` as `null`
    cheaply, if you only care about the point importances.

    Also returns `plausibility_check`: compares the forecast's implied
    endpoint change against the empirical distribution of horizon-length
    changes the series has actually made historically, flagging
    `is_extreme_relative_to_history` and whether the forecast ever leaves
    the historical min/max range.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        horizon: Number of future steps to forecast.
        lags: List of lag steps to use as features. Defaults to [1, 7, 14].
        n_estimators: Number of boosting stages.
        max_depth: Max depth per tree.
        learning_rate: Shrinkage rate applied to each tree's contribution.
        confidence_level: Width of the quantile-regression prediction interval AND the feature-importance CI, e.g. 0.95 for 95%.
        n_bootstrap: Bootstrap resamples for the feature-importance CI. 0 skips it (cheap).
        seed: Random seed for the feature-importance bootstrap, for reproducibility.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _forecast_gradient_boosted_trees(
        df,
        horizon=horizon,
        lags=lags,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        confidence_level=confidence_level,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )


@mcp.tool()
def forecast_ensemble(
    csv_path: str,
    model_types: list,
    horizon: int = 30,
    weights: Optional[list] = None,
    model_params: Optional[dict] = None,
    confidence_level: float = 0.95,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Combine two or more of this layer's own forecasts (naive/ets/sarima/gbt)
    into a single weighted forecast -- the tool for "what should I actually
    deploy" when more than one backtest-validated candidate looks reasonable,
    rather than being forced to pick exactly one.

    weights defaults to equal weighting across model_types; if supplied, must
    match model_types in length, be non-negative, and needn't be
    pre-normalized (e.g. pass raw inverse-MAE values straight from a Layer 2
    backtest_metrics comparison -- they get normalized internally). The
    combined point forecast is a weighted average at each future date. The
    combined interval (when every component contributes one) is a VARIANCE
    combination -- each component's own interval width becomes an implied
    standard deviation, combined via sqrt(sum(w_i^2 * sigma_i^2)) assuming
    the components' errors are INDEPENDENT, then rebuilt around the
    weighted point forecast. More principled than a plain bound average,
    but the independence assumption is optimistic (every component is fit
    on the SAME series), so treat this as a lower bound on the ensemble's
    true uncertainty -- it can come out narrower than any single
    component's own interval, which is the expected effect of combining
    independent estimates, not a bug. See interval_note.

    Also returns `plausibility_check`, computed on the COMBINED weighted
    forecast: compares its implied endpoint change against the empirical
    distribution of horizon-length changes the series has actually made
    historically, flagging `is_extreme_relative_to_history` and whether
    the combined forecast ever leaves the historical min/max range.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        model_types: List of 2+ model types to combine, from "naive", "ets", "sarima", "gbt".
        horizon: Number of future steps to forecast.
        weights: Optional weight per model_type entry (same order, same length). Equal if omitted.
        model_params: Optional per-model_type kwargs override, e.g.
            {"sarima": {"order": [1,1,1], "seasonal_order": [1,1,1,7]}}.
        confidence_level: Width of each component's own prediction interval, e.g. 0.95 for 95%.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _forecast_ensemble(
        df,
        model_types=model_types,
        horizon=horizon,
        weights=weights,
        model_params=model_params,
        confidence_level=confidence_level,
    )


@mcp.tool()
def plot_forecast(
    csv_path: str,
    forecast: list,
    out_path: Optional[str] = None,
    date_col: str = "date",
    value_col: str = "value",
) -> ToolResult:
    """Plot a series' history plus a deployed forecast_* result's own
    trajectory, with a shaded interval band wherever the forecast points
    carry lower/upper bounds. Returns the image INLINE (rendered directly
    in this response, visible immediately) as well as, if `out_path` is
    given, saved to disk.

    This is a visual complement to forecast_naive/forecast_ets/
    forecast_sarima/forecast_gradient_boosted_trees's own numbers, never
    a replacement for them -- the interval band, the point trajectory,
    the plausibility_check flag all still come from those tools' real
    JSON output. Use this to SHOW that same forecast, not to re-derive it.

    Args:
        csv_path: Path to the historical series CSV (the same one the
            forecast_* call used).
        forecast: The `forecast` list from a forecast_* result, passed
            through exactly as returned (including any truncation-note
            placeholder entry for horizon > 60 -- it's skipped here).
        out_path: If given, also writes the PNG to this path on disk.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _plot_forecast(df, forecast, out_path=out_path)


def main() -> None:
    """Entry point for the `ts-deploy-server` console script."""
    mcp.run()  # defaults to stdio transport, which is what OpenClaw expects


if __name__ == "__main__":
    main()
