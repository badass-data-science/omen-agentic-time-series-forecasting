"""
plot_tools.py

Layer 3 plotting: visual feedback for a real forecast_* result, never a
replacement for its exact numbers. Takes the SAME forecast list a
forecast_* call already produced (not model params -- this doesn't
re-run a forecast, it draws the one you already have).
"""

from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd
from fastmcp.tools.tool import ToolResult

from omen.plotting import render_plot


def plot_forecast(
    df: pd.DataFrame,
    forecast: list,
    out_path: Optional[str] = None,
) -> ToolResult:
    """Plot a series' history plus a deployed forecast_* result's own
    forecast trajectory, with a shaded interval band wherever the
    forecast points carry lower/upper bounds.

    `forecast` is exactly the `forecast` field a forecast_naive/
    forecast_ets/forecast_sarima/forecast_gradient_boosted_trees call
    already returned -- a list of {date, forecast, lower?, upper?}
    dicts. For horizon > 60, that list can include a single
    truncation-note placeholder dict ({"note": "N more days omitted..."})
    in the middle (see _format_forecast in forecast_tools.py) -- those
    are skipped here rather than plotted, since there's nothing to draw
    for an omitted stretch and the gap in dates would otherwise look
    like a real break in the underlying data.

    Args:
        df: Historical series (date, value columns).
        forecast: The forecast list from a forecast_* result.
        out_path: If given, also writes the PNG to this path on disk.
    """
    points = [p for p in forecast if "forecast" in p]

    fc_dates = pd.to_datetime([p["date"] for p in points])
    fc_values = [p["forecast"] for p in points]
    has_interval = all("lower" in p and "upper" in p for p in points) and len(points) > 0

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df["date"], df["value"], color="tab:blue", label="History", linewidth=1.2)
    ax.plot(fc_dates, fc_values, color="tab:orange", label="Forecast", linewidth=1.5)

    if has_interval:
        lower = [p["lower"] for p in points]
        upper = [p["upper"] for p in points]
        ax.fill_between(fc_dates, lower, upper, color="tab:orange", alpha=0.2, label="Interval")

    ax.axvline(df["date"].iloc[-1], color="gray", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Date")
    ax.set_ylabel("Value")
    ax.set_title("Forecast")
    ax.legend(loc="upper left")
    fig.autofmt_xdate()

    n_omitted = sum(1 for p in forecast if "forecast" not in p)
    return render_plot(
        fig,
        out_path=out_path,
        n_history_points=len(df),
        n_forecast_points_plotted=len(points),
        n_forecast_points_omitted=n_omitted,
        has_interval=has_interval,
    )
