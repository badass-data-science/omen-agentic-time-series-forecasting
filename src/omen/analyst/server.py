"""
server.py — FastMCP server for the time series analyst tools.

Wraps the same diagnostic logic from analysis_tools.py as typed MCP tools,
so any MCP client (OpenClaw, Claude Desktop, Claude Code, etc.) can call
them with validated arguments instead of composing shell commands.

Run directly for local testing (after `pip install -e .`):
    ts-analyst-server
    # or: python -m omen.analyst.server

Run over stdio (how OpenClaw / most MCP clients will actually launch it):
    this IS the stdio entrypoint by default — see mcp.run() at the bottom.
"""

from typing import Optional

from fastmcp import FastMCP

from .analysis_tools import (
    basic_stats as _basic_stats,
    check_stationarity as _check_stationarity,
    seasonal_decomposition_summary as _seasonal_decomposition_summary,
    detect_seasonality_period as _detect_seasonality_period,
    acf_pacf_summary as _acf_pacf_summary,
    detect_anomalies_zscore as _detect_anomalies_zscore,
    detect_anomalies_robust_zscore as _detect_anomalies_robust_zscore,
    detect_changepoints as _detect_changepoints,
)
from .plot_tools import (
    plot_series as _plot_series,
    plot_acf_pacf as _plot_acf_pacf,
    plot_seasonal_decomposition as _plot_seasonal_decomposition,
    plot_periodogram as _plot_periodogram,
    plot_anomalies as _plot_anomalies,
    plot_changepoints as _plot_changepoints,
)
from omen.data_prep import generate_synthetic_series, load_series

mcp = FastMCP("ts-analyst")


@mcp.tool()
def generate_synthetic_data(out_path: str = "/tmp/ts_data.csv", n_days: int = 730) -> dict:
    """Generate a synthetic daily time series (trend + weekly/yearly
    seasonality + noise + a few injected anomalies) and write it to CSV.
    Use this when the user hasn't provided their own data to analyze.

    Args:
        out_path: Where to write the generated CSV.
        n_days: How many daily observations to generate.
    """
    df = generate_synthetic_series(n_days=n_days)
    df.to_csv(out_path, index=False)
    return {
        "status": "ok",
        "written_to": out_path,
        "n_rows": len(df),
        "start_date": str(df["date"].min().date()),
        "end_date": str(df["date"].max().date()),
    }


@mcp.tool()
def basic_stats(
    csv_path: str,
    confidence_level: float = 0.95,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Get summary statistics for a time series CSV: length, date range,
    missing values, and mean/std/min/max of the value column. Also returns
    a confidence interval for the mean (mean_ci_lower, mean_ci_upper, via
    Student's t) -- a bare mean invites reading small differences as more
    meaningful than the sample size actually supports.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        confidence_level: Confidence level for the mean's interval, e.g.
            0.95 for 95%.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _basic_stats(df, confidence_level=confidence_level)


@mcp.tool()
def check_stationarity(
    csv_path: str,
    kpss_regression: str = "c",
    confidence_level: float = 0.95,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Run BOTH an Augmented Dickey-Fuller test and a KPSS test to check
    whether a time series is stationary, combined into one joint verdict
    (the two tests have opposite null hypotheses, so running both and
    reading them together is standard practice -- see `interpretation`
    for the four-way readout, e.g. what it means if they disagree).

    Also returns two effect sizes, since neither test's p-value alone
    says how strongly (not just whether) the series behaves that way:
    - mean_reversion_lambda / mean_reversion_half_life_periods (ADF-based),
      each with a confidence interval (mean_reversion_lambda_ci_lower/
      _upper, mean_reversion_half_life_ci_lower/_upper): a series can be
      statistically stationary yet revert so slowly the half-life is
      impractically long for short-horizon forecasting, and the point
      estimate alone overstates how precisely that half-life is known.
      half_life_ci_upper is null when the interval is unbounded (lambda's
      own CI reaches non-reverting territory).
    - kpss_effect_size (KPSS statistic / its 5% critical value): stays
      informative even when KPSS's own p-value is clipped at a
      lookup-table boundary (a real limitation of that test in practice).

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        kpss_regression: "c" (default, stationary around a constant) or
            "ct" (stationary around a deterministic trend). Use "ct" if
            ADF and KPSS disagree in a way that suggests trend-stationarity.
        confidence_level: Confidence level for the mean-reversion
            lambda/half-life interval, e.g. 0.95 for 95%.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _check_stationarity(df, kpss_regression=kpss_regression, confidence_level=confidence_level)


@mcp.tool()
def seasonal_decomposition_summary(
    csv_path: str,
    period: int = 7,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Decompose a time series into trend/seasonal/residual components and
    return the relative strength of the trend and seasonal components.
    Use period=7 for daily data with weekly seasonality, period=12 for
    monthly data with yearly seasonality, etc.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        period: Assumed seasonal period, in number of observations.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _seasonal_decomposition_summary(df, period=period)


@mcp.tool()
def detect_seasonality_period(
    csv_path: str,
    min_period: int = 2,
    max_period: Optional[int] = None,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Find the dominant cyclical period in a series via its periodogram,
    with a significance test (Fisher's g-test for hidden periodicity) --
    so you don't have to already know/guess a period before calling
    seasonal_decomposition_summary or reading acf_pacf_summary's
    significant lags for a periodic pattern. Ranks candidate periods
    within [min_period, max_period] (default max_period = n // 2) by
    relative spectral power, an effect size in its own right. Check
    dominant_period_in_reported_range before treating the significance
    test as endorsing one of the reported candidates specifically -- the
    single globally strongest frequency can correspond to a period
    outside that range (e.g. trend, or a very short edge-effect period).

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        min_period: Smallest period (in observations) worth reporting as
            a candidate. A period must repeat at least twice to be a
            meaningful cycle.
        max_period: Largest period worth reporting. Defaults to half the
            series length (periods near the series length aren't
            distinguishable from trend).
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _detect_seasonality_period(df, min_period=min_period, max_period=max_period)


@mcp.tool()
def acf_pacf_summary(
    csv_path: str,
    n_lags: int = 21,
    alpha: float = 0.05,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Get autocorrelation and partial autocorrelation values, and which
    lags are statistically significant, using PER-LAG confidence intervals
    (statsmodels' Bartlett formula) rather than a single global threshold
    -- the correct standard error for ACF grows with lag, since it depends
    on the cumulative autocorrelation of earlier lags. Useful for
    identifying seasonality period and candidate AR/MA order. Each
    significant lag in significant_acf_lags includes its own confidence
    interval (ci_lower, ci_upper) and an effect_size (the ACF magnitude as
    a multiple of its own interval half-width), sorted strongest first,
    since "significant" alone doesn't distinguish a barely-significant lag
    from one that's 5x its own threshold.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        n_lags: Number of lags to check.
        alpha: Significance level for the per-lag confidence intervals,
            e.g. 0.05 for 95% intervals.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _acf_pacf_summary(df, n_lags=n_lags, alpha=alpha)


@mcp.tool()
def detect_anomalies_zscore(
    csv_path: str,
    z_threshold: float = 3.0,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Flag observations that deviate sharply (by z_threshold standard
    deviations or more) from a local rolling mean — a simple anomaly /
    outlier detector. Each flagged point in `anomalies` includes its actual
    z_score, sorted most extreme first, since a z-score of 3.1 and one of
    11 both just clear a threshold of 3.0 but are very different findings.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        z_threshold: Number of standard deviations from the rolling mean
            to flag as anomalous.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _detect_anomalies_zscore(df, z_threshold=z_threshold)


@mcp.tool()
def detect_anomalies_robust_zscore(
    csv_path: str,
    z_threshold: float = 3.5,
    window: int = 14,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Robust anomaly detection using a rolling MODIFIED z-score (rolling
    median + MAD, Iglewicz & Hoya 1993) instead of detect_anomalies_zscore's
    rolling mean + std. detect_anomalies_zscore's rolling std is distorted
    by the very anomaly it's trying to measure -- a single large spike
    inside its rolling window inflates that window's own std, diluting
    the z-score of the point that caused it. Median/MAD are far less
    sensitive to a single outlier within a window, so this doesn't have
    that self-dilution problem. Default z_threshold is 3.5, not 3.0 --
    the Iglewicz & Hoya-recommended default for the modified z-score
    specifically, not copied from the non-robust version.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        z_threshold: Modified z-score magnitude to flag as anomalous.
        window: Rolling window size (centered) for the local median/MAD.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _detect_anomalies_robust_zscore(df, z_threshold=z_threshold, window=window)


@mcp.tool()
def detect_changepoints(
    csv_path: str,
    alpha: float = 0.05,
    min_segment_size: int = 10,
    max_changepoints: int = 5,
    n_permutations: int = 500,
    seed: int = 42,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Detect structural breaks (lasting shifts in the series' MEAN
    LEVEL) using binary segmentation with a CUSUM statistic and a
    permutation test for significance -- a different job from
    detect_anomalies_zscore/detect_anomalies_robust_zscore, which flag
    individual POINT outliers, not a persistent shift from one regime to
    the next. Each changepoint reports Cohen's d (pooled-std standardized
    mean difference between the segments immediately before/after) as an
    effect size. KNOWN LIMITATION: binary segmentation's per-split
    p-values are local tests, not an exact global significance guarantee
    for the full set of changepoints reported -- a standard, accepted
    tradeoff for this class of algorithm. Results are deterministic given
    the same seed.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        alpha: Significance level for each split's permutation test.
        min_segment_size: Minimum observations required on each side of
            a candidate split; also the minimum resulting segment size.
        max_changepoints: Upper bound on how many changepoints to report.
        n_permutations: Permutations used per significance test. Higher
            is more precise but slower.
        seed: Random seed for the permutation test's shuffling, for
            reproducibility.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _detect_changepoints(
        df,
        alpha=alpha,
        min_segment_size=min_segment_size,
        max_changepoints=max_changepoints,
        n_permutations=n_permutations,
        seed=seed,
    )


@mcp.tool()
def plot_series(
    csv_path: str,
    out_path: Optional[str] = None,
    date_col: str = "date",
    value_col: str = "value",
):
    """Plot the raw value-vs-date series -- visual companion to
    basic_stats, never a replacement for its exact numbers. Missing
    values show as visible GAPS in the line, not interpolated over.
    Returns the plot inline (always) plus, if out_path is given, also
    writes it there as a PNG.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        out_path: If given, also saves the plot as a PNG at this path.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _plot_series(df, out_path=out_path)


@mcp.tool()
def plot_acf_pacf(
    csv_path: str,
    n_lags: int = 21,
    alpha: float = 0.05,
    out_path: Optional[str] = None,
    date_col: str = "date",
    value_col: str = "value",
):
    """Plot ACF and PACF side by side, with the SAME per-lag Bartlett
    significance bands acf_pacf_summary reports (shared computation, not
    reimplemented) -- visual companion to that tool, never a replacement
    for its exact per-lag effect sizes.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        n_lags: Number of lags to plot.
        alpha: Significance level for the per-lag confidence bands.
        out_path: If given, also saves the plot as a PNG at this path.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _plot_acf_pacf(df, n_lags=n_lags, alpha=alpha, out_path=out_path)


@mcp.tool()
def plot_seasonal_decomposition(
    csv_path: str,
    period: int = 7,
    out_path: Optional[str] = None,
    date_col: str = "date",
    value_col: str = "value",
):
    """Plot the additive trend/seasonal/residual decomposition as a
    vertically stacked subplot -- visual companion to
    seasonal_decomposition_summary, never a replacement for its exact
    strength scores.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        period: Assumed seasonal period, in number of observations.
        out_path: If given, also saves the plot as a PNG at this path.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _plot_seasonal_decomposition(df, period=period, out_path=out_path)


@mcp.tool()
def plot_periodogram(
    csv_path: str,
    min_period: int = 2,
    max_period: Optional[int] = None,
    out_path: Optional[str] = None,
    date_col: str = "date",
    value_col: str = "value",
):
    """Plot periodogram power vs. period, marking both the single
    globally strongest frequency and the top in-range candidate
    distinctly -- makes it visually obvious when the two differ (e.g.
    the globally strongest frequency is really just the series' own
    trend, outside the sensible seasonality range). Visual companion to
    detect_seasonality_period, never a replacement for its exact
    significance test.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        min_period: Smallest period worth marking as a candidate.
        max_period: Largest period worth marking. Defaults to half the
            series length.
        out_path: If given, also saves the plot as a PNG at this path.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _plot_periodogram(df, min_period=min_period, max_period=max_period, out_path=out_path)


@mcp.tool()
def plot_anomalies(
    csv_path: str,
    z_threshold: float = 3.5,
    window: int = 14,
    out_path: Optional[str] = None,
    date_col: str = "date",
    value_col: str = "value",
):
    """Plot the series with points flagged by the ROBUST (median+MAD)
    anomaly detector marked -- visual companion to
    detect_anomalies_robust_zscore, never a replacement for its exact
    modified z-scores.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        z_threshold: Modified z-score magnitude to flag as anomalous.
        window: Rolling window size (centered) for the local median/MAD.
        out_path: If given, also saves the plot as a PNG at this path.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _plot_anomalies(df, z_threshold=z_threshold, window=window, out_path=out_path)


@mcp.tool()
def plot_changepoints(
    csv_path: str,
    alpha: float = 0.05,
    min_segment_size: int = 10,
    max_changepoints: int = 5,
    n_permutations: int = 500,
    seed: int = 42,
    out_path: Optional[str] = None,
    date_col: str = "date",
    value_col: str = "value",
):
    """Plot the series with detected changepoints as vertical lines,
    segments shaded alternately -- visual companion to
    detect_changepoints, never a replacement for its exact CUSUM
    statistics/p-values.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        alpha: Significance level for each split's permutation test.
        min_segment_size: Minimum observations required on each side of
            a candidate split.
        max_changepoints: Upper bound on how many changepoints to plot.
        n_permutations: Permutations used per significance test.
        seed: Random seed for the permutation test's shuffling.
        out_path: If given, also saves the plot as a PNG at this path.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _plot_changepoints(
        df,
        alpha=alpha,
        min_segment_size=min_segment_size,
        max_changepoints=max_changepoints,
        n_permutations=n_permutations,
        seed=seed,
        out_path=out_path,
    )


def main():
    """Entry point for the `ts-analyst-server` console script."""
    mcp.run()  # defaults to stdio transport, which is what OpenClaw expects


if __name__ == "__main__":
    main()
