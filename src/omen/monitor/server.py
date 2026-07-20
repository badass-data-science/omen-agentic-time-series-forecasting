"""
server.py — FastMCP server for the Layer 4 monitoring tools.

Closes the loop after ts-deploy: once real observations exist for at least
part of a forecast's horizon, checks whether the forecast is still
tracking reality, whether the data has drifted, and combines both into a
retrain recommendation.

Run over stdio (how OpenClaw will launch it), after `pip install -e .`:
    ts-monitor-server
    # or: python -m omen.monitor.server
"""

from typing import Optional

from fastmcp import FastMCP

from omen.data_prep import load_series
from .monitor_tools import (
    compare_forecast_to_actuals as _compare_forecast_to_actuals,
    detect_data_drift as _detect_data_drift,
    recommend_retraining as _recommend_retraining,
)

mcp = FastMCP("ts-monitor")


@mcp.tool()
def compare_forecast_to_actuals(
    forecast: list,
    csv_path: str,
    confidence_level: float = 0.95,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Match a previously produced forecast against real observed values
    now present in the updated series CSV, and report error metrics over
    whatever portion of the horizon has actually elapsed, plus prediction
    interval coverage if the forecast included one.

    Args:
        forecast: The `forecast` list from a ts-deploy tool's result
            (list of {date, forecast, lower?, upper?} dicts). Pass it
            through exactly as returned.
        csv_path: Path to the UPDATED series CSV -- must contain real
            observations for at least some of the forecasted dates.
        confidence_level: The forecast's nominal confidence level, e.g.
            0.95, used to judge whether interval coverage looks calibrated.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _compare_forecast_to_actuals(forecast, df, confidence_level=confidence_level)


@mcp.tool()
def detect_data_drift(
    csv_path: str,
    recent_window_size: int = 30,
    reference_window_size: int = 90,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Compare the most recent `recent_window_size` observations against a
    reference window taken immediately before it, using a t-test (mean
    shift) and a KS test (distribution shape). Flags possible drift, but
    can't distinguish an ongoing trend or normal seasonal transition from a
    genuine regime change -- read the `interpretation` field, don't treat
    `drift_detected` as an automatic alarm.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        recent_window_size: Number of most-recent observations to treat as "now."
        reference_window_size: Number of observations immediately before
            the recent window, used as the comparison baseline.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _detect_data_drift(df, recent_window_size=recent_window_size, reference_window_size=reference_window_size)


@mcp.tool()
def recommend_retraining(
    mape_now: float,
    mape_backtest: float,
    drift_detected: bool,
    interval_coverage_pct: Optional[float] = None,
    nominal_confidence_pct: Optional[float] = None,
    error_degradation_threshold_pct: float = 20.0,
    coverage_miscalibration_threshold_pct: float = 15.0,
) -> dict:
    """Deterministic decision combining forecast-error degradation and
    data drift into a retrain recommendation (retrain_now / investigate /
    monitor_closely / no_action_needed). This is intentionally rule-based
    rather than left to model judgment, since "should we retrain" is the
    kind of decision worth being reproducible given the same inputs.

    Args:
        mape_now: MAPE of the forecast against real recent observations,
            from compare_forecast_to_actuals's backtest_style_metrics.
        mape_backtest: The original Layer 2 backtest MAPE for this same
            model type/settings.
        drift_detected: The drift_detected flag from detect_data_drift.
        interval_coverage_pct: Empirical prediction interval coverage, if
            compare_forecast_to_actuals returned one.
        nominal_confidence_pct: The interval's nominal confidence level,
            if available (e.g. 95.0).
        error_degradation_threshold_pct: How much worse (relative %)
            mape_now can be than mape_backtest before counting as degraded.
        coverage_miscalibration_threshold_pct: How far empirical coverage
            can be from nominal before counting as miscalibrated.
    """
    return _recommend_retraining(
        mape_now=mape_now,
        mape_backtest=mape_backtest,
        drift_detected=drift_detected,
        interval_coverage_pct=interval_coverage_pct,
        nominal_confidence_pct=nominal_confidence_pct,
        error_degradation_threshold_pct=error_degradation_threshold_pct,
        coverage_miscalibration_threshold_pct=coverage_miscalibration_threshold_pct,
    )


def main():
    """Entry point for the `ts-monitor-server` console script."""
    mcp.run()  # defaults to stdio transport, which is what OpenClaw expects


if __name__ == "__main__":
    main()
