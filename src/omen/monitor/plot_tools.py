"""
plot_tools.py

Layer 4 plotting: visual feedback for the monitoring tools, never a
replacement for their exact numbers. Every plot here reuses the real
monitor_tools.py computation internally rather than reimplementing it,
so the picture can never silently disagree with the JSON.
"""

import matplotlib.pyplot as plt
import pandas as pd

from omen.plotting import render_plot
from .monitor_tools import compare_forecast_to_actuals, detect_data_drift


def plot_forecast_vs_actuals(
    forecast: list,
    df: pd.DataFrame,
    out_path: str = None,
) -> "ToolResult":
    """Plot a deployed forecast's trajectory (with interval band, if it
    has one) against the real observed actuals that have since arrived.

    Reuses compare_forecast_to_actuals's own date-matching internally
    (same forecast/df arguments, same shape) rather than re-matching
    dates independently -- the matched points plotted here are exactly
    the ones that tool's own backtest_style_metrics were computed from.

    Args:
        forecast: The `forecast` list from a forecast_* result.
        df: The UPDATED series (must contain real observations for at
            least some of the forecasted dates).
        out_path: If given, also writes the PNG to this path on disk.
    """
    comparison = compare_forecast_to_actuals(forecast, df)
    if "error" in comparison:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, comparison["error"], ha="center", va="center", wrap=True)
        ax.axis("off")
        return render_plot(fig, out_path=out_path, status="error", error=comparison["error"])

    matched = comparison["matched_points"]
    dates = pd.to_datetime([m["date"] for m in matched])
    actual = [m["actual"] for m in matched]
    fc = [m["forecast"] for m in matched]
    has_interval = all(m.get("lower") is not None and m.get("upper") is not None for m in matched)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, fc, color="tab:orange", label="Forecast", linewidth=1.5, marker="o", markersize=3)
    ax.plot(dates, actual, color="tab:blue", label="Actual", linewidth=1.5, marker="o", markersize=3)

    if has_interval:
        lower = [m["lower"] for m in matched]
        upper = [m["upper"] for m in matched]
        ax.fill_between(dates, lower, upper, color="tab:orange", alpha=0.2, label="Interval")

    ax.set_xlabel("Date")
    ax.set_ylabel("Value")
    ax.set_title("Forecast vs. Actuals")
    ax.legend(loc="best")
    fig.autofmt_xdate()

    return render_plot(
        fig,
        out_path=out_path,
        n_dates_compared=comparison["n_dates_compared"],
        has_interval=has_interval,
    )


def plot_drift(
    df: pd.DataFrame,
    recent_window_size: int = 30,
    reference_window_size: int = 90,
    out_path: str = None,
) -> "ToolResult":
    """Plot the recent window's and reference window's value distributions
    side by side, annotated with detect_data_drift's own real Cohen's d
    and drift verdict (computed by calling that function internally, not
    reimplemented here).

    Args:
        df: The series to check.
        recent_window_size: Same meaning as detect_data_drift's own arg.
        reference_window_size: Same meaning as detect_data_drift's own arg.
        out_path: If given, also writes the PNG to this path on disk.
    """
    result = detect_data_drift(df, recent_window_size=recent_window_size, reference_window_size=reference_window_size)
    if "error" in result:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.text(0.5, 0.5, result["error"], ha="center", va="center", wrap=True)
        ax.axis("off")
        return render_plot(fig, out_path=out_path, status="error", error=result["error"])

    total_needed = recent_window_size + reference_window_size
    recent = df["value"].iloc[-recent_window_size:].values
    reference = df["value"].iloc[-total_needed:-recent_window_size].values

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot([reference, recent], tick_labels=["Reference", "Recent"])
    cohens_d = result["mean_shift_cohens_d"]
    d_str = f"{cohens_d:.2f}" if cohens_d is not None else "N/A"
    ax.set_title(
        f"Drift check: {'FLAGGED' if result['drift_detected'] else 'not flagged'} "
        f"(Cohen's d={d_str})"
    )
    ax.set_ylabel("Value")

    return render_plot(
        fig,
        out_path=out_path,
        drift_detected=result["drift_detected"],
        mean_shift_cohens_d=cohens_d,
    )


def plot_rolling_drift(checks: list, out_path: str = None) -> "ToolResult":
    """Plot Cohen's d across rolling_drift_check's own walk-forward
    checks, marking which ones flagged drift.

    Args:
        checks: The `checks` list from a rolling_drift_check result,
            passed through exactly as returned.
        out_path: If given, also writes the PNG to this path on disk.
    """
    successful = [c for c in checks if "error" not in c]
    labels = [c["recent_window_end_date"] for c in successful]
    values = [c["mean_shift_cohens_d"] for c in successful]
    flagged = [c["drift_detected"] for c in successful]
    colors = ["tab:red" if f else "tab:gray" for f in flagged]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(range(len(labels)), values, color=colors)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Cohen's d")
    ax.set_title("Rolling drift check (red = flagged)")
    ax.axhline(0, color="black", linewidth=0.8)

    return render_plot(
        fig,
        out_path=out_path,
        n_checks_plotted=len(successful),
        n_flagged=sum(flagged),
    )
