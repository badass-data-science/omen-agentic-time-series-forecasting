"""
plot_tools.py

Layer-1 plotting tools: visual companions to analysis_tools.py's JSON
diagnostics, never a replacement for them. Each plot_* function here
reuses the SAME underlying computation its JSON counterpart uses
(either by calling that function directly, or via a small shared
private helper both call) so the picture and the numbers can never
silently disagree.

Plain functions, matching analysis_tools.py's split: server.py wraps
these as @mcp.tool() and handles CSV loading. Every function ends by
handing a finished matplotlib Figure to omen.plotting.render_plot,
which returns it as an inline image (plus an optional on-disk PNG if
out_path is given).
"""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import periodogram
from statsmodels.tsa.seasonal import seasonal_decompose

from omen.plotting import render_plot
from .analysis_tools import (
    _acf_pacf_raw,
    detect_seasonality_period,
    detect_anomalies_zscore,
    detect_anomalies_robust_zscore,
    detect_changepoints,
)


def plot_series(df: pd.DataFrame, out_path: str = None):
    """Plot the raw value-vs-date series. Missing values show as visible
    GAPS in the line (not interpolated over) -- basic_stats already
    treats missing data as a first-class finding in this project, so the
    plot shouldn't paper over it either.
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["date"], df["value"], linewidth=1.2, color="tab:blue")
    n_missing = int(df["value"].isna().sum())
    ax.set_title(f"Series ({len(df)} observations, {n_missing} missing)")
    ax.set_xlabel("date")
    ax.set_ylabel("value")
    fig.autofmt_xdate()
    return render_plot(fig, out_path=out_path, n_observations=len(df), n_missing=n_missing)


def plot_acf_pacf(df: pd.DataFrame, n_lags: int = 21, alpha: float = 0.05, out_path: str = None):
    """Plot ACF and PACF as two stem plots side by side, with the SAME
    per-lag Bartlett significance bands acf_pacf_summary reports (shared
    computation via _acf_pacf_raw, not reimplemented) -- lags whose bar
    crosses outside the shaded band are the ones acf_pacf_summary would
    flag as significant.
    """
    acf_vals, acf_confint, pacf_vals, n_lags = _acf_pacf_raw(df, n_lags, alpha)
    lags = np.arange(len(acf_vals))

    fig, (ax_acf, ax_pacf) = plt.subplots(1, 2, figsize=(12, 4))

    ax_acf.stem(lags, acf_vals, basefmt=" ")
    # Bartlett bands, centered on each lag's own ACF value (per-lag, not global).
    ax_acf.fill_between(lags, acf_confint[:, 0], acf_confint[:, 1], alpha=0.2, color="tab:blue")
    ax_acf.axhline(0, color="black", linewidth=0.8)
    ax_acf.set_title("ACF (shaded = Bartlett CI per lag)")
    ax_acf.set_xlabel("lag")

    pacf_lags = np.arange(len(pacf_vals))
    ax_pacf.stem(pacf_lags, pacf_vals, basefmt=" ", linefmt="tab:orange", markerfmt="o")
    ax_pacf.axhline(0, color="black", linewidth=0.8)
    ax_pacf.set_title("PACF")
    ax_pacf.set_xlabel("lag")

    fig.tight_layout()
    return render_plot(fig, out_path=out_path, n_lags=int(n_lags))


def plot_seasonal_decomposition(df: pd.DataFrame, period: int = 7, out_path: str = None):
    """Plot the additive trend/seasonal/residual decomposition as a
    vertically stacked subplot -- the same seasonal_decompose call
    seasonal_decomposition_summary's strength scores are computed from.
    """
    series = df.set_index("date")["value"]
    if len(series) < period * 2:
        raise ValueError(f"Series too short to decompose with period={period}.")

    decomposition = seasonal_decompose(series, model="additive", period=period, extrapolate_trend="freq")

    fig, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=True)
    axes[0].plot(series.index, series.values, color="tab:blue")
    axes[0].set_ylabel("observed")
    axes[1].plot(decomposition.trend.index, decomposition.trend.values, color="tab:green")
    axes[1].set_ylabel("trend")
    axes[2].plot(decomposition.seasonal.index, decomposition.seasonal.values, color="tab:orange")
    axes[2].set_ylabel("seasonal")
    axes[3].scatter(decomposition.resid.index, decomposition.resid.values, s=8, color="tab:red")
    axes[3].axhline(0, color="black", linewidth=0.8)
    axes[3].set_ylabel("residual")
    axes[0].set_title(f"Additive decomposition (period={period})")
    fig.autofmt_xdate()
    fig.tight_layout()
    return render_plot(fig, out_path=out_path, period_assumed=period)


def plot_periodogram(df: pd.DataFrame, min_period: int = 2, max_period: int = None, out_path: str = None):
    """Plot periodogram power vs. period, marking both the single
    globally strongest frequency (which can be a trend/edge artifact --
    the finding detect_seasonality_period's dominant_period_in_reported_range
    flag exists to catch) and the top in-range candidate distinctly, so
    the two are never confused visually.

    Calls detect_seasonality_period() for the authoritative summary
    (dominant_period, top candidate, significance) and separately
    computes the raw periodogram curve (same scipy.signal.periodogram
    call that function uses internally) purely for the visual -- the
    summary numbers always come from the real tool, never re-derived.
    """
    summary = detect_seasonality_period(df, min_period=min_period, max_period=max_period)
    if "error" in summary:
        raise ValueError(summary["error"])

    series = df["value"].dropna().to_numpy(dtype=float)
    demeaned = series - series.mean()
    freqs, power = periodogram(demeaned)
    freqs, power = freqs[1:], power[1:]
    periods = 1.0 / freqs

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(periods, power, color="tab:blue", linewidth=1.0)
    ax.axvline(
        summary["dominant_period"],
        color="tab:red",
        linestyle="--",
        label=f"global strongest (period~{summary['dominant_period']})",
    )
    if summary["top_candidate_periods"]:
        top_in_range = summary["top_candidate_periods"][0]["period"]
        if top_in_range != summary["dominant_period"]:
            ax.axvline(
                top_in_range,
                color="tab:green",
                linestyle=":",
                label=f"top in-range candidate (period~{top_in_range})",
            )
    ax.set_xlabel("period")
    ax.set_ylabel("power")
    ax.set_title("Periodogram")
    ax.legend()
    fig.tight_layout()
    return render_plot(
        fig,
        out_path=out_path,
        dominant_period=summary["dominant_period"],
        dominant_period_in_reported_range=summary["dominant_period_in_reported_range"],
    )


def plot_anomalies(df: pd.DataFrame, z_threshold: float = 3.5, window: int = 14, out_path: str = None):
    """Plot the series with points flagged by the ROBUST (median+MAD)
    anomaly detector marked -- reuses detect_anomalies_robust_zscore's
    own output (this project's recommended default over the plain
    z-score version, since it doesn't self-dilute on the very anomaly
    it's trying to flag) rather than recomputing flags independently.
    """
    result = detect_anomalies_robust_zscore(df, z_threshold=z_threshold, window=window)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["date"], df["value"], linewidth=1.0, color="tab:blue", zorder=1)
    if result["anomalies"]:
        flagged_dates = pd.to_datetime([a["date"] for a in result["anomalies"]])
        flagged_values = [a["value"] for a in result["anomalies"]]
        ax.scatter(flagged_dates, flagged_values, color="tab:red", s=40, zorder=2, label="flagged anomaly")
        ax.legend()
    ax.set_title(f"Anomalies (robust modified z-score, threshold={z_threshold})")
    ax.set_xlabel("date")
    ax.set_ylabel("value")
    fig.autofmt_xdate()
    return render_plot(fig, out_path=out_path, n_anomalies_flagged=result["n_anomalies_flagged"])


def plot_changepoints(
    df: pd.DataFrame,
    alpha: float = 0.05,
    min_segment_size: int = 10,
    max_changepoints: int = 5,
    n_permutations: int = 500,
    seed: int = 42,
    out_path: str = None,
):
    """Plot the series with detected changepoints as vertical lines,
    segments shaded alternately -- reuses detect_changepoints' own
    output (the same CUSUM/permutation-test results) rather than
    recomputing changepoints independently.
    """
    result = detect_changepoints(
        df,
        alpha=alpha,
        min_segment_size=min_segment_size,
        max_changepoints=max_changepoints,
        n_permutations=n_permutations,
        seed=seed,
    )
    if "error" in result:
        raise ValueError(result["error"])

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["date"], df["value"], linewidth=1.2, color="tab:blue", zorder=2)

    boundaries = [df["date"].iloc[0]] + [pd.Timestamp(cp["date"]) for cp in result["changepoints"]] + [df["date"].iloc[-1]]
    for i in range(len(boundaries) - 1):
        if i % 2 == 1:
            ax.axvspan(boundaries[i], boundaries[i + 1], color="gray", alpha=0.12, zorder=0)
    for cp in result["changepoints"]:
        ax.axvline(pd.Timestamp(cp["date"]), color="tab:red", linestyle="--", zorder=1)

    ax.set_title(f"{result['n_changepoints_found']} changepoint(s) detected (alpha={alpha})")
    ax.set_xlabel("date")
    ax.set_ylabel("value")
    fig.autofmt_xdate()
    return render_plot(fig, out_path=out_path, n_changepoints_found=result["n_changepoints_found"])
