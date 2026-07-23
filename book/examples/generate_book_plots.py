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
    grumbling_level,
    mojito_inventory,
    mojito_inventory_clean,
    mojito_inventory_month2_actuals,
    mojito_inventory_constant,
    mad_degenerate_edge_case,
    deathray_revenue,
    deathray_revenue_rival,
    deathray_revenue_slow_month,
    drycleaning_bills,
    drycleaning_bills_steep_trend,
    power_consumption,
    interpol_attention,
    interpol_attention_shifted,
    interpol_attention_train,
    self_destruct_timer,
    minion_overtime,
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


def grumbling_level_series(out_dir):
    """Chapter 2: the 5-point installation smoke test, plotted raw."""
    plot_series(grumbling_level(), out_path=os.path.join(out_dir, "grumbling_level_series.png"))


def mojito_inventory_constant_series(out_dir):
    """Chapter 3: the zero-variance edge case -- a flat week, plotted raw."""
    plot_series(mojito_inventory_constant(), out_path=os.path.join(out_dir, "mojito_inventory_constant_series.png"))


def deathray_revenue_series(out_dir):
    """Chapter 4 (reused 8-13, 15, 18): the flagship Death-Ray Revenue
    series, plotted raw for the first time -- 70 weeks, strong upward
    trend, no orientation plot existed for this series until now."""
    plot_series(deathray_revenue(), out_path=os.path.join(out_dir, "deathray_revenue_series.png"))


def drycleaning_bills_series(out_dir):
    """Chapter 5: the raw dry-cleaning bills series, before decomposition
    or periodogram analysis -- the annual cycle visible by eye."""
    plot_series(drycleaning_bills(), out_path=os.path.join(out_dir, "drycleaning_bills_series.png"))


def drycleaning_bills_steep_trend_series(out_dir):
    """Chapter 5's gotcha variant: the same series with a 10x steeper
    trend, plotted raw so the trend's visual dominance is obvious before
    the periodogram trap is demonstrated."""
    plot_series(drycleaning_bills_steep_trend(), out_path=os.path.join(out_dir, "drycleaning_bills_steep_trend_series.png"))


def power_consumption_series(out_dir):
    """Chapter 7: the raw power consumption series, spike and baseline
    shift both visible by eye, before the anomaly/changepoint tools run."""
    plot_series(power_consumption(), out_path=os.path.join(out_dir, "power_consumption_series.png"))


def deathray_revenue_slow_month_series(out_dir):
    """Chapter 8's MAPE-vs-MAE variant: the supplementary series with the
    four-week revenue freeze, plotted raw so the flat-zero stretch is
    visible before the metric comparison."""
    plot_series(deathray_revenue_slow_month(), out_path=os.path.join(out_dir, "deathray_revenue_slow_month_series.png"))


def minion_overtime_series(out_dir):
    """Chapter 11: the raw Minion Overtime Hours series, weekly cycle
    visible by eye, before feature engineering/GBT fitting begins."""
    plot_series(minion_overtime(), out_path=os.path.join(out_dir, "minion_overtime_series.png"))


def mojito_inventory_clean_series(out_dir):
    """Chapter 14: the interpolated, deployment-ready mojito series on
    its own -- no gaps left, distinct from mojito_inventory_series.png's
    raw (gappy) version."""
    plot_series(mojito_inventory_clean(), out_path=os.path.join(out_dir, "mojito_inventory_clean_series.png"))


def mad_degenerate_edge_case_series(out_dir):
    """Chapter 16's constructed MAD-degenerate example, plotted raw --
    a flat run of actuals, the shape that later drives the residual
    outlier check's MAD to exactly 0."""
    plot_series(mad_degenerate_edge_case(), out_path=os.path.join(out_dir, "mad_degenerate_edge_case_series.png"))


def mojito_inventory_month2_actuals_series(out_dir):
    """Chapter 16's real month-2 actuals on their own -- distinct from
    mojito_forecast_vs_actuals.png, which overlays them against the
    deployed forecast rather than showing the actuals alone."""
    plot_series(mojito_inventory_month2_actuals(), out_path=os.path.join(out_dir, "mojito_inventory_month2_actuals_series.png"))


def interpol_attention_series(out_dir):
    """Chapter 17: the raw Interpol Attention Level series, the ordinary
    upward trend visible by eye before any drift check runs."""
    plot_series(interpol_attention(), out_path=os.path.join(out_dir, "interpol_attention_series.png"))


def interpol_attention_shifted_series(out_dir):
    """Chapter 17's real escalation variant, plotted raw -- the +300
    level shift in the final 8 weeks visible directly, distinct from
    interpol_drift_shifted.png's distribution boxplot."""
    plot_series(interpol_attention_shifted(), out_path=os.path.join(out_dir, "interpol_attention_shifted_series.png"))


def interpol_attention_train_series(out_dir):
    """Chapter 17's pre-escalation training history (first 83 of 91
    weeks), plotted raw -- what a deployed model would have seen before
    the real +300 shift happened."""
    plot_series(interpol_attention_train(), out_path=os.path.join(out_dir, "interpol_attention_train_series.png"))


def deathray_revenue_rival_series(out_dir):
    """Chapter 18's rival-extended series, plotted raw -- the trend
    visibly flattening in the final weeks where the price war begins."""
    plot_series(deathray_revenue_rival(), out_path=os.path.join(out_dir, "deathray_revenue_rival_series.png"))


def self_destruct_timer_series(out_dir):
    """Chapter 19: the raw Self-Destruct Countdown Timer Adjustments
    series -- a modest, gently declining series, plotted for orientation
    even though this chapter isn't about forecasting it well."""
    plot_series(self_destruct_timer(), out_path=os.path.join(out_dir, "self_destruct_timer_series.png"))


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
    "grumbling_level_series": grumbling_level_series,
    "mojito_inventory_constant_series": mojito_inventory_constant_series,
    "deathray_revenue_series": deathray_revenue_series,
    "drycleaning_bills_series": drycleaning_bills_series,
    "drycleaning_bills_steep_trend_series": drycleaning_bills_steep_trend_series,
    "power_consumption_series": power_consumption_series,
    "deathray_revenue_slow_month_series": deathray_revenue_slow_month_series,
    "minion_overtime_series": minion_overtime_series,
    "mojito_inventory_clean_series": mojito_inventory_clean_series,
    "mad_degenerate_edge_case_series": mad_degenerate_edge_case_series,
    "mojito_inventory_month2_actuals_series": mojito_inventory_month2_actuals_series,
    "interpol_attention_series": interpol_attention_series,
    "interpol_attention_shifted_series": interpol_attention_shifted_series,
    "interpol_attention_train_series": interpol_attention_train_series,
    "deathray_revenue_rival_series": deathray_revenue_rival_series,
    "self_destruct_timer_series": self_destruct_timer_series,
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
