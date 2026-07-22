"""
generate_book_plots.py

Regenerates every named plot image used in "Agentic Time Series
Forecasting for Supervillains" -- the visual counterpart to
generate_book_datasets.py. Every plot here is built from that same
script's own dataset functions (or a real tool call on top of one of
them, using the exact model/window parameters already established in
that chapter's own published numbers), then rendered through the real
plot_* tools this project ships -- not a hand-drawn approximation.

Re-running this script reproduces the same real images (the underlying
numbers are exactly reproducible; matplotlib's own pixel-level
rendering can vary slightly across matplotlib versions, same caveat as
any figure-generation script).

Usage:
    python generate_book_plots.py                # writes every image to ./images/
    python generate_book_plots.py --out DIR       # writes to a different directory
    python generate_book_plots.py --only mojito_inventory_series,ch10_sarima_search

Requires Omen installed with the extras every plotted tool needs
(pip install -e ".[all]" from the project root covers all of them).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_book_datasets import (
    mojito_inventory,
    mojito_inventory_clean,
    mojito_inventory_month2_actuals,
    deathray_revenue,
    drycleaning_bills,
    drycleaning_bills_steep_trend,
    power_consumption,
    interpol_attention,
    interpol_attention_shifted,
)

from omen.analyst.plot_tools import (
    plot_series,
    plot_acf_pacf,
    plot_seasonal_decomposition,
    plot_periodogram,
    plot_anomalies,
    plot_changepoints,
)
from omen.forecaster.model_tools import (
    fit_naive_baselines,
    search_sarima_orders,
    rolling_origin_backtest,
)
from omen.forecaster.plot_tools import (
    plot_backtest,
    plot_rolling_origin,
    plot_search_sarima_orders,
)
from omen.deploy.forecast_tools import forecast_sarima
from omen.deploy.plot_tools import plot_forecast
from omen.monitor.monitor_tools import rolling_drift_check
from omen.monitor.plot_tools import plot_forecast_vs_actuals, plot_drift, plot_rolling_drift


def _mojito_sarima_forecast():
    """Chapter 14's real deployed forecast -- shared by mojito_sarima_forecast
    and mojito_forecast_vs_actuals, since both plot the exact same call."""
    df = mojito_inventory_clean()
    return forecast_sarima(df, horizon=30, order=[1, 1, 1], seasonal_order=[1, 1, 1, 7])["forecast"]


def mojito_inventory_series(out_dir):
    """Chapter 3: the raw mojito series, gaps visible where 5 days are missing."""
    plot_series(mojito_inventory(), out_path=os.path.join(out_dir, "mojito_inventory_series.png"))


def drycleaning_bills_decomposition(out_dir):
    """Chapter 5: trend/seasonal/residual decomposition, 52-week period."""
    plot_seasonal_decomposition(
        drycleaning_bills(), period=52,
        out_path=os.path.join(out_dir, "drycleaning_bills_decomposition.png"),
    )


def drycleaning_bills_periodogram(out_dir):
    """Chapter 5: the clean case -- dominant period correctly found within
    the plausible 10-60 week range the chapter searches over."""
    plot_periodogram(
        drycleaning_bills(), min_period=10, max_period=60,
        out_path=os.path.join(out_dir, "drycleaning_bills_periodogram.png"),
    )


def drycleaning_bills_steep_periodogram(out_dir):
    """Chapter 5: the trap -- a steeper trend variant, same 10-60 range."""
    plot_periodogram(
        drycleaning_bills_steep_trend(), min_period=10, max_period=60,
        out_path=os.path.join(out_dir, "drycleaning_bills_steep_periodogram.png"),
    )


def drycleaning_bills_acf_pacf(out_dir):
    """Chapter 6: ACF/PACF with Bartlett bands, default n_lags."""
    plot_acf_pacf(drycleaning_bills(), out_path=os.path.join(out_dir, "drycleaning_bills_acf_pacf.png"))


def power_consumption_anomalies(out_dir):
    """Chapter 7: the +500 spike, flagged by the robust detector, default params."""
    plot_anomalies(power_consumption(), out_path=os.path.join(out_dir, "power_consumption_anomalies.png"))


def power_consumption_changepoints(out_dir):
    """Chapter 7: the +80 baseline shift, default params."""
    plot_changepoints(power_consumption(), out_path=os.path.join(out_dir, "power_consumption_changepoints.png"))


def ch08_naive_backtests(out_dir):
    """Chapter 8: naive (17.46% MAPE) and seasonal-naive (19.98% MAPE)
    backtests on Death-Ray Revenue, two separate plots since plot_backtest
    takes one predicted series at a time."""
    result = fit_naive_baselines(deathray_revenue(), holdout_size=30)
    actuals = result["holdout_actuals"]
    plot_backtest(
        actuals, result["naive"]["holdout_predicted"], model_name="Naive",
        out_path=os.path.join(out_dir, "ch08_naive_backtest.png"),
    )
    plot_backtest(
        actuals, result["seasonal_naive"]["holdout_predicted"], model_name="Seasonal-Naive",
        out_path=os.path.join(out_dir, "ch08_seasonal_naive_backtest.png"),
    )


def ch10_sarima_search(out_dir):
    """Chapter 10: the real 9-combination search, d=1 fixed, no seasonal
    terms -- the razor-thin AICc margin between the top two candidates."""
    result = search_sarima_orders(
        deathray_revenue(), holdout_size=30, d=1, seasonal_d=0,
        max_p=2, max_q=2, max_seasonal_p=0, max_seasonal_q=0,
    )
    plot_search_sarima_orders(result["top_candidates"], out_path=os.path.join(out_dir, "ch10_sarima_search.png"))


def ch13_rolling_origin(out_dir):
    """Chapter 13: SARIMA(1,1,2)'s real 5-origin walk-forward MAPE swing
    (0.86% to 8.77%)."""
    result = rolling_origin_backtest(
        deathray_revenue(), model_type="sarima",
        params={"order": [1, 1, 2], "seasonal_order": [0, 0, 0, 2]},
        holdout_size=10, n_origins=5,
    )
    plot_rolling_origin(result["origins"], out_path=os.path.join(out_dir, "ch13_rolling_origin.png"))


def mojito_sarima_forecast(out_dir):
    """Chapter 14: the real deployed SARIMA forecast, history + trajectory
    + interval band."""
    df = mojito_inventory_clean()
    forecast = _mojito_sarima_forecast()
    plot_forecast(df, forecast, out_path=os.path.join(out_dir, "mojito_sarima_forecast.png"))


def mojito_forecast_vs_actuals(out_dir):
    """Chapter 16: the same forecast, checked against real month-2 actuals
    (including the real party-night spike on 2024-07-15)."""
    forecast = _mojito_sarima_forecast()
    plot_forecast_vs_actuals(
        forecast, mojito_inventory_month2_actuals(),
        out_path=os.path.join(out_dir, "mojito_forecast_vs_actuals.png"),
    )


def interpol_drift_plain(out_dir):
    """Chapter 17: the plain trending series -- real Cohen's d 1.45,
    "large" by conventional bins despite being an ordinary trend."""
    plot_drift(
        interpol_attention(), recent_window_size=8, reference_window_size=26,
        out_path=os.path.join(out_dir, "interpol_drift_plain.png"),
    )


def interpol_drift_shifted(out_dir):
    """Chapter 17: the real +300 escalation -- Cohen's d 11.91."""
    plot_drift(
        interpol_attention_shifted(), recent_window_size=8, reference_window_size=26,
        out_path=os.path.join(out_dir, "interpol_drift_shifted.png"),
    )


def interpol_rolling_drift(out_dir):
    """Chapter 17: the real 5-check rolling walk (3.03, 2.43, 1.92, 1.36, 1.45)."""
    result = rolling_drift_check(
        interpol_attention(), recent_window_size=8, reference_window_size=26, n_checks=5,
    )
    plot_rolling_drift(result["checks"], out_path=os.path.join(out_dir, "interpol_rolling_drift.png"))


PLOTS = {
    "mojito_inventory_series": mojito_inventory_series,
    "drycleaning_bills_decomposition": drycleaning_bills_decomposition,
    "drycleaning_bills_periodogram": drycleaning_bills_periodogram,
    "drycleaning_bills_steep_periodogram": drycleaning_bills_steep_periodogram,
    "drycleaning_bills_acf_pacf": drycleaning_bills_acf_pacf,
    "power_consumption_anomalies": power_consumption_anomalies,
    "power_consumption_changepoints": power_consumption_changepoints,
    "ch08_naive_backtests": ch08_naive_backtests,
    "ch10_sarima_search": ch10_sarima_search,
    "ch13_rolling_origin": ch13_rolling_origin,
    "mojito_sarima_forecast": mojito_sarima_forecast,
    "mojito_forecast_vs_actuals": mojito_forecast_vs_actuals,
    "interpol_drift_plain": interpol_drift_plain,
    "interpol_drift_shifted": interpol_drift_shifted,
    "interpol_rolling_drift": interpol_rolling_drift,
}


def main():
    parser = argparse.ArgumentParser(description="Regenerate every named plot image used in the book.")
    parser.add_argument("--out", type=str, default="images", help="Directory to write PNGs into.")
    parser.add_argument("--only", type=str, default=None, help="Comma-separated plot names to regenerate (default: all).")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    names = args.only.split(",") if args.only else list(PLOTS.keys())

    for name in names:
        if name not in PLOTS:
            raise SystemExit(f"Unknown plot '{name}'. Choices: {list(PLOTS.keys())}")
        PLOTS[name](args.out)
        print(f"Wrote plot(s) for '{name}' to {args.out}/")


if __name__ == "__main__":
    main()
