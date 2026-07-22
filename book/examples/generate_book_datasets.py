"""
generate_book_datasets.py

Regenerates every named example dataset used in "Forecasting for
Supervillains," exactly as it was generated for the chapter that first
introduces it. Every generation call here uses a fixed seed, so running
this script reproduces the exact same CSVs -- and, run through the same
Omen tools shown in each chapter, the exact same numbers -- every time.

This exists specifically because a book that shows real, live tool
output has to let readers regenerate that same output themselves, not
just trust that the numbers on the page were real once. If you're
reading a chapter and want to reproduce (or poke at) the series it's
using, run this file.

Usage:
    python generate_book_datasets.py            # writes every dataset to ./data/
    python generate_book_datasets.py --out DIR   # writes to a different directory

Requires Omen installed (pip install -e ".[all]" from the project root,
or at least the omen.data_prep module, which has no extra dependencies
beyond numpy/pandas).
"""

import argparse
import os

import numpy as np
import pandas as pd

from omen.data_prep import generate_synthetic_series


def _weekly_resample(daily: pd.DataFrame) -> pd.DataFrame:
    """Aggregate a daily series into weekly totals, dropping the first
    and last (partial) weeks. Used by every "weekly spend/revenue"
    example in the book, which are all built from a daily generator and
    then summed up -- see each chapter for why."""
    indexed = daily.set_index("date")
    weekly = indexed["value"].resample("W-MON", label="left", closed="left").sum().reset_index()
    weekly.columns = ["date", "value"]
    return weekly.iloc[1:-1].reset_index(drop=True)


def grumbling_level() -> pd.DataFrame:
    """Chapter 2's installation smoke test: 'Secret Lab(tm) Weekly
    Grumbling Level,' five hardcoded days, deliberately too small to
    mean anything statistically -- the point is proving the MCP
    connection works, not that the forecasting is good."""
    return pd.DataFrame({
        "date": pd.date_range("2026-07-14", periods=5, freq="D"),
        "value": [3, 4, 4, 6, 5],
    })


def mojito_inventory() -> pd.DataFrame:
    """Chapter 3's flagship series: 182 days (~6 months) of Secret
    Lab(tm) mojito inventory, with 5 days blanked out to represent
    "the incident" -- teaches basic_stats and the non-missing-count
    confidence interval gotcha. Deployed for real in Chapter 14."""
    df = generate_synthetic_series(n_days=182, seed=42, base_level=200.0)
    rng = np.random.default_rng(7)
    incident_idx = sorted(rng.choice(range(30, 150), size=5, replace=False))
    df.loc[incident_idx, "value"] = np.nan
    return df


def mojito_inventory_clean() -> pd.DataFrame:
    """Chapter 14's deployment-ready series: mojito_inventory() with its
    5 missing days linearly interpolated -- the fix for the chapter's
    own opening gotcha, where deploying straight from the raw CSV
    silently produced an all-null forecast with no error raised. Round-
    trips through CSV text first, matching the real workflow (read the
    raw CSV, then interpolate) byte-for-byte -- interpolating the
    in-memory, not-yet-serialized values instead gives float64 results
    that differ from the CSV-sourced ones in their last one or two
    significant digits."""
    import io
    buf = io.StringIO()
    mojito_inventory().to_csv(buf, index=False)
    buf.seek(0)
    df = pd.read_csv(buf, parse_dates=["date"])
    df["value"] = df["value"].interpolate(method="linear")
    return df


def mojito_inventory_constant() -> pd.DataFrame:
    """Chapter 3's zero-variance edge case: a week where the mojito
    count never changed, to show the honest null/null confidence
    interval rather than a fabricated zero-width one."""
    return pd.DataFrame({
        "date": pd.date_range("2024-01-01", periods=7, freq="D"),
        "value": [200] * 7,
    })


def deathray_revenue() -> pd.DataFrame:
    """Chapters 4, 8-13, 15, 18: 70 weeks of Death-Ray Revenue, weekly
    income from renting out the Secret Lab(tm)'s death ray, built with a
    strong upward trend -- the book's flagship deliberately
    non-stationary series."""
    daily = generate_synthetic_series(
        n_days=500,
        seed=42,
        base_level=2000.0,
        trend_per_day=6.0,
        weekly_amplitude=150.0,
        yearly_amplitude=100.0,
        noise_std=120.0,
    )
    return _weekly_resample(daily)


def deathray_revenue_slow_month() -> pd.DataFrame:
    """Chapter 8's MAPE-vs-MAE demonstration: a shorter, supplementary
    Death-Ray Revenue series where four consecutive weeks of exactly $0
    revenue (a rival's cease-and-desist freezing bookings) sit inside the
    backtest holdout -- shows mape_points_excluded_near_zero actually
    firing, and MAE catching a disaster that MAPE alone would hide."""
    daily = generate_synthetic_series(
        n_days=350,
        seed=42,
        base_level=2000.0,
        trend_per_day=6.0,
        weekly_amplitude=150.0,
        yearly_amplitude=100.0,
        noise_std=120.0,
    )
    weekly = _weekly_resample(daily)
    freeze_idx = [len(weekly) - 8, len(weekly) - 7, len(weekly) - 6, len(weekly) - 5]
    weekly.loc[freeze_idx, "value"] = 0.0
    return weekly


def drycleaning_bills() -> pd.DataFrame:
    """Chapters 5-6: 155 weeks (~3 years) of Henchman Costume
    Dry-Cleaning Bills, with a genuine annual (Halloween) cycle and a
    modest trend -- the clean case where detect_seasonality_period
    correctly finds the true ~52-week cycle unassisted."""
    daily = generate_synthetic_series(
        n_days=1095,
        seed=42,
        base_level=300.0,
        trend_per_day=0.3,
        weekly_amplitude=20.0,
        yearly_amplitude=250.0,
        noise_std=25.0,
    )
    return _weekly_resample(daily)


def drycleaning_bills_steep_trend() -> pd.DataFrame:
    """Chapter 5's gotcha demonstration: the same dry-cleaning series,
    regenerated with a 10x steeper trend, strong enough that the
    periodogram's single strongest frequency becomes the trend itself
    (period = full series length) rather than the true annual cycle."""
    daily = generate_synthetic_series(
        n_days=1095,
        seed=42,
        base_level=300.0,
        trend_per_day=3.0,
        weekly_amplitude=20.0,
        yearly_amplitude=250.0,
        noise_std=25.0,
    )
    return _weekly_resample(daily)


def power_consumption() -> pd.DataFrame:
    """Chapter 7: 250 days of Secret Lab(tm) Power Consumption, with a
    real injected +500 single-day spike (the death ray misfire, day
    index 100) and a separate, later +80 permanent baseline shift (the
    annexed rival lair, day index 150 onward) -- one series containing
    both an anomaly and a changepoint on purpose."""
    df = generate_synthetic_series(
        n_days=250,
        seed=42,
        base_level=200.0,
        trend_per_day=0.05,
        weekly_amplitude=15.0,
        yearly_amplitude=10.0,
        noise_std=10.0,
    )
    df.loc[100, "value"] += 500.0
    df.loc[150:, "value"] += 80.0
    return df


def minion_overtime() -> pd.DataFrame:
    """Chapter 11: 400 days of Minion Overtime Hours, with a strong
    weekly cycle (weekend cover) and a milder yearly one (year-end
    quota scramble) -- built to make lag_7 dominate gradient-boosted
    trees' feature importances, and to show month's crude categorical
    bucketing losing most of that same yearly signal."""
    df = generate_synthetic_series(
        n_days=400,
        seed=42,
        base_level=8.0,
        trend_per_day=0.01,
        weekly_amplitude=4.0,
        yearly_amplitude=3.5,
        noise_std=1.2,
    )
    df["value"] = df["value"].clip(lower=0)
    return df


DATASETS = {
    "grumbling_level": grumbling_level,
    "mojito_inventory": mojito_inventory,
    "mojito_inventory_clean": mojito_inventory_clean,
    "mojito_inventory_constant": mojito_inventory_constant,
    "deathray_revenue": deathray_revenue,
    "deathray_revenue_slow_month": deathray_revenue_slow_month,
    "drycleaning_bills": drycleaning_bills,
    "drycleaning_bills_steep_trend": drycleaning_bills_steep_trend,
    "power_consumption": power_consumption,
    "minion_overtime": minion_overtime,
}


def main():
    parser = argparse.ArgumentParser(description="Regenerate every named dataset used in the book.")
    parser.add_argument("--out", type=str, default="data", help="Directory to write CSVs into.")
    parser.add_argument("--only", type=str, default=None, help="Comma-separated dataset names to regenerate (default: all).")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    names = args.only.split(",") if args.only else list(DATASETS.keys())

    for name in names:
        if name not in DATASETS:
            raise SystemExit(f"Unknown dataset '{name}'. Choices: {list(DATASETS.keys())}")
        df = DATASETS[name]()
        path = os.path.join(args.out, f"{name}.csv")
        df.to_csv(path, index=False)
        print(f"Wrote {path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
