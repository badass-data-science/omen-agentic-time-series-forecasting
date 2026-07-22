"""
data_prep.py

Provides a time series to experiment with. By default it generates a
synthetic daily series with trend + weekly seasonality + yearly seasonality +
noise + a few injected anomalies (holiday-like spikes), which gives the
agent something realistic to reason about.

Swap in your own data by pointing load_series() at a CSV with a date column
and a value column.
"""

from typing import Optional

import numpy as np
import pandas as pd


def generate_synthetic_series(
    n_days: int = 730,
    start_date: str = "2024-01-01",
    base_level: float = 200.0,
    trend_per_day: float = 0.15,
    weekly_amplitude: float = 30.0,
    yearly_amplitude: float = 50.0,
    noise_std: float = 10.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a synthetic daily demand series with trend, weekly and yearly
    seasonality, Gaussian noise, and a handful of injected spikes/dips to
    mimic promotions or outages.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start_date, periods=n_days, freq="D")

    t = np.arange(n_days)
    trend = base_level + trend_per_day * t
    weekly = weekly_amplitude * np.sin(2 * np.pi * t / 7.0)
    yearly = yearly_amplitude * np.sin(2 * np.pi * t / 365.25)
    noise = rng.normal(0, noise_std, size=n_days)

    values = trend + weekly + yearly + noise

    # Inject a few anomalies: promo-like spikes and an outage-like dip
    anomaly_idx = rng.choice(n_days, size=max(3, n_days // 150), replace=False)
    for idx in anomaly_idx:
        direction = rng.choice([-1, 1])
        magnitude = rng.uniform(2.5, 4.0) * noise_std
        values[idx] += direction * magnitude

    values = np.clip(values, a_min=0, a_max=None)

    df = pd.DataFrame({"date": dates, "value": values})
    return df


def load_series(csv_path: Optional[str] = None, date_col: str = "date", value_col: str = "value") -> pd.DataFrame:
    """Load a time series from CSV, or fall back to the synthetic generator
    if no path is given. Returns a DataFrame with columns ['date', 'value'],
    sorted by date, with 'date' as a proper datetime dtype.
    """
    if csv_path is None:
        return generate_synthetic_series()

    df = pd.read_csv(csv_path)
    df = df.rename(columns={date_col: "date", value_col: "value"})
    df["date"] = pd.to_datetime(df["date"])
    df = df[["date", "value"]].sort_values("date").reset_index(drop=True)
    return df


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Generate a synthetic time series CSV for analysis.")
    parser.add_argument("--out", type=str, default="ts_data.csv", help="Where to write the CSV.")
    parser.add_argument("--n-days", type=int, default=730)
    args = parser.parse_args()

    df = generate_synthetic_series(n_days=args.n_days)
    df.to_csv(args.out, index=False)
    print(json.dumps({
        "status": "ok",
        "written_to": args.out,
        "n_rows": len(df),
        "start_date": str(df["date"].min().date()),
        "end_date": str(df["date"].max().date()),
    }))
