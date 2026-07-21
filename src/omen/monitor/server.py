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
    rolling_drift_check as _rolling_drift_check,
    recommend_retraining as _recommend_retraining,
)

mcp = FastMCP("ts-monitor")


@mcp.tool()
def compare_forecast_to_actuals(
    forecast: list,
    csv_path: str,
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    seed: int = 42,
    outlier_z_threshold: float = 3.5,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Match a previously produced forecast against real observed values
    now present in the updated series CSV, and report error metrics over
    whatever portion of the horizon has actually elapsed, plus prediction
    interval coverage if the forecast included one.

    `backtest_style_metrics` now includes a bootstrap confidence interval
    for MAE/RMSE/MAPE (mae_ci_lower/upper, etc., percentile method,
    deterministic given `seed`) alongside the point estimates -- a
    comparison drawn from just a few elapsed forecast dates has real
    sampling uncertainty of its own, same reasoning as ts-forecaster's
    backtest metric CIs. Pass `mape_pct_ci_lower`/`mape_pct_ci_upper` from
    here straight through to `recommend_retraining`'s
    `mape_now_ci_lower`/`mape_now_ci_upper` if you want the degradation
    verdict to flag when it's sensitive to this sampling noise.

    `interval_coverage` (when available) now also includes
    `empirical_coverage_ci_lower`/`empirical_coverage_ci_upper` (a Wilson
    score CI on the coverage percentage itself) -- supplementary
    information only, it does NOT change `well_calibrated`'s existing
    threshold-based verdict, but a wide CI here means the calibration
    read is provisional given how few dates have elapsed so far.

    `residual_outliers` flags matched-point residuals (actual - forecast)
    that look like outliers via a modified z-score (same technique as
    ts-analyst's detect_anomalies_robust_zscore): `flagged_dates` (which
    dates, if any), `max_abs_modified_z_score`, and per-point detail in
    `per_point`. It also reports `metrics_excluding_outliers` so you can
    see whether the aggregate error above is being driven by a small
    number of unusual days rather than a systematic miss -- these call
    for different responses when deciding whether to retrain.

    Args:
        forecast: The `forecast` list from a ts-deploy tool's result
            (list of {date, forecast, lower?, upper?} dicts). Pass it
            through exactly as returned.
        csv_path: Path to the UPDATED series CSV -- must contain real
            observations for at least some of the forecasted dates.
        confidence_level: The forecast's nominal confidence level, e.g.
            0.95, used both to judge interval coverage calibration AND as
            the width of the bootstrap CI on the error metrics.
        n_bootstrap: Bootstrap resamples for the error-metric CIs.
        seed: Random seed for the bootstrap, for reproducibility.
        outlier_z_threshold: Modified z-score threshold for flagging a
            matched-point residual as an outlier.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _compare_forecast_to_actuals(
        forecast, df, confidence_level=confidence_level, n_bootstrap=n_bootstrap, seed=seed, outlier_z_threshold=outlier_z_threshold
    )


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

    Also returns `mean_shift_cohens_d` (pooled-SD effect size for the mean
    shift) and the raw `ttest_statistic`/`ks_statistic` the two tests are
    built on -- a bare p-value doesn't distinguish a barely-significant
    shift from a drastic one, same reasoning behind every other effect
    size in this project. `ks_statistic` (0 to 1) is itself already a
    natural magnitude: the maximum distance between the two windows'
    empirical CDFs.

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
def rolling_drift_check(
    csv_path: str,
    recent_window_size: int = 30,
    reference_window_size: int = 90,
    n_checks: int = 5,
    step_size: Optional[int] = None,
    persistence_threshold_frac: float = 0.5,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Repeats detect_data_drift at n_checks different points walking
    backward through the series, instead of trusting the single most-recent
    recent/reference split alone. Addresses the "one arbitrary window"
    fragility a single detect_data_drift call has -- a single split might
    have caught an ordinary one-off blip rather than a sustained shift.
    Cheap per check (no model fitting), so a larger n_checks costs little;
    the real constraint is having enough historical data to walk back
    through (see the tool's error message for the exact requirement).

    Returns `n_flagged`/`frac_flagged` (how many of the successful checks
    flagged drift, and what fraction that is) and `persistent_drift`:
    true when `frac_flagged` is at least `persistence_threshold_frac`,
    meaning the shift shows up consistently across time rather than in
    just one window.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        recent_window_size: Test window size at each check.
        reference_window_size: Reference window size at each check.
        n_checks: How many non-overlapping checks to run, walking backward.
        step_size: How far back each successive check's recent window
            starts. Defaults to recent_window_size (non-overlapping).
        persistence_threshold_frac: Fraction of successful checks that
            must flag drift before `persistent_drift` is true.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _rolling_drift_check(
        df,
        recent_window_size=recent_window_size,
        reference_window_size=reference_window_size,
        n_checks=n_checks,
        step_size=step_size,
        persistence_threshold_frac=persistence_threshold_frac,
    )


@mcp.tool()
def recommend_retraining(
    mape_now: float,
    mape_backtest: float,
    drift_detected: bool,
    interval_coverage_pct: Optional[float] = None,
    nominal_confidence_pct: Optional[float] = None,
    mape_now_ci_lower: Optional[float] = None,
    mape_now_ci_upper: Optional[float] = None,
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
        mape_now_ci_lower: Optional bootstrap CI lower bound on mape_now
            (compare_forecast_to_actuals's backtest_style_metrics.mape_pct_ci_lower).
            If supplied alongside mape_now_ci_upper, the result reports the
            implied degradation range as `pct_degradation_ci_lower`/
            `pct_degradation_ci_upper`, and flags `degradation_threshold_within_ci: true`
            when the threshold itself falls inside that range -- i.e. the
            degraded/not-degraded verdict is sensitive to sampling noise in
            mape_now, not clear-cut.
        mape_now_ci_upper: See mape_now_ci_lower (mape_pct_ci_upper).
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
        mape_now_ci_lower=mape_now_ci_lower,
        mape_now_ci_upper=mape_now_ci_upper,
        error_degradation_threshold_pct=error_degradation_threshold_pct,
        coverage_miscalibration_threshold_pct=coverage_miscalibration_threshold_pct,
    )


def main():
    """Entry point for the `ts-monitor-server` console script."""
    mcp.run()  # defaults to stdio transport, which is what OpenClaw expects


if __name__ == "__main__":
    main()
