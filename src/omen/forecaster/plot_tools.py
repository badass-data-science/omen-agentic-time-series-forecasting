"""
plot_tools.py

Layer 2 plotting functions: visual complements to model_tools.py's own
exact numbers, never a replacement for them. Unlike model_tools.py's
functions (which take a DataFrame + holdout_size and fit fresh), these
take the ALREADY-COMPUTED arrays/lists a prior fit_*/diebold_mariano_test/
rolling_origin_backtest/search_sarima_orders call already produced --
same "pass the array forward directly" convention diebold_mariano_test
itself already uses, so plotting never silently re-runs an expensive fit.
"""

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from omen.plotting import render_plot


def plot_backtest(
    actuals: list,
    predicted: list,
    model_name: str = "Model",
    lower: Optional[list] = None,
    upper: Optional[list] = None,
    out_path: Optional[str] = None,
):
    """Plot actual vs. predicted values over a backtest holdout, with a
    shaded prediction-interval band if lower/upper bounds are supplied.

    Pass the SAME holdout_actuals/holdout_predicted a fit_* result
    already returned (the same arrays diebold_mariano_test takes) --
    this does not refit anything. lower/upper are optional since not
    every model has an interval (e.g. fit_gradient_boosted_trees's
    backtest has none); when omitted, only the two lines are drawn.
    """
    actuals = np.asarray(actuals, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    x = np.arange(1, len(actuals) + 1)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(x, actuals, label="Actual", color="black", linewidth=1.5, marker="o", markersize=3)
    ax.plot(x, predicted, label=f"{model_name} (predicted)", color="tab:blue", linewidth=1.5, marker="o", markersize=3)

    has_interval = lower is not None and upper is not None
    if has_interval:
        lower_arr = np.asarray(lower, dtype=float)
        upper_arr = np.asarray(upper, dtype=float)
        ax.fill_between(x, lower_arr, upper_arr, color="tab:blue", alpha=0.15, label="Prediction interval")

    ax.set_xlabel("Holdout step")
    ax.set_ylabel("Value")
    ax.set_title(f"Backtest: Actual vs. {model_name}")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()

    return render_plot(fig, out_path=out_path, n_points_plotted=len(actuals), interval_shown=has_interval)


def plot_rolling_origin(origins: list, out_path: Optional[str] = None):
    """Plot per-origin MAPE across a rolling_origin_backtest's walk-forward
    origins, with a shaded band showing the mean +/- one std across
    origins -- makes cross-origin instability (a model whose accuracy
    swings a lot depending on which stretch of the series it's tested
    against) visually obvious rather than requiring a reader to compare
    a table of numbers.

    Pass rolling_origin_backtest's own `origins` field directly --
    already-failed origins (entries with an "error" key instead of
    mape_pct) are skipped, not plotted as zero.
    """
    successful = [o for o in origins if "error" not in o and o.get("mape_pct") is not None]
    if not successful:
        raise ValueError("No successful origins with a mape_pct to plot.")

    x = np.arange(1, len(successful) + 1)
    mape = np.array([o["mape_pct"] for o in successful], dtype=float)
    labels = [
        o.get("test_range", [None, None])[-1] or f"origin {o.get('origin_index', i)}"
        for i, o in enumerate(successful)
    ]

    mean = float(np.mean(mape))
    std = float(np.std(mape, ddof=1)) if len(mape) > 1 else 0.0

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x, mape, color="tab:blue", alpha=0.75, label="MAPE per origin")
    ax.axhline(mean, color="black", linestyle="--", linewidth=1, label=f"Mean ({mean:.2f}%)")
    if std > 0:
        ax.axhspan(mean - std, mean + std, color="black", alpha=0.08, label="+/- 1 std")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
    ax.set_xlabel("Origin (test window end date)")
    ax.set_ylabel("MAPE (%)")
    ax.set_title("Rolling-Origin Backtest: MAPE Stability Across Origins")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()

    return render_plot(fig, out_path=out_path, n_origins_plotted=len(successful), mape_pct_mean=round(mean, 4), mape_pct_std=round(std, 4))


def plot_search_sarima_orders(top_candidates: list, out_path: Optional[str] = None):
    """Plot AICc by candidate SARIMA order as a bar chart, so a razor-thin
    margin between the top candidates (which a table of decimals can
    hide) is visually obvious.

    Pass search_sarima_orders' own `top_candidates` field directly.
    Candidates with no aicc (too little data relative to parameter
    count) fall back to plotting aic instead, labeled accordingly.
    """
    if not top_candidates:
        raise ValueError("top_candidates is empty -- nothing to plot.")

    labels = []
    values = []
    used_aic_fallback = False
    for c in top_candidates:
        order = tuple(c["order"])
        seasonal_order = tuple(c["seasonal_order"])
        labels.append(f"{order}{seasonal_order}")
        v = c.get("aicc")
        if v is None:
            v = c.get("aic")
            used_aic_fallback = True
        values.append(v)

    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(6, 1.2 * len(labels)), 4.5))
    colors = ["tab:green" if i == 0 else "tab:blue" for i in range(len(labels))]
    ax.bar(x, values, color=colors)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
    ax.set_ylabel("AICc" if not used_aic_fallback else "AICc (or AIC where unavailable)")
    ax.set_title("SARIMA Order Search: Candidates Ranked by AICc")
    if len(values) > 1:
        # Zoom the y-axis to the candidates' actual spread rather than
        # starting at 0 -- a bar chart from zero visually erases exactly
        # the kind of razor-thin margin this plot exists to surface.
        span = max(values) - min(values)
        pad = span * 0.15 if span > 0 else max(abs(min(values)), 1) * 0.01
        ax.set_ylim(min(values) - pad, max(values) + pad)
    fig.tight_layout()

    return render_plot(fig, out_path=out_path, n_candidates_plotted=len(labels), best_order=labels[0])
