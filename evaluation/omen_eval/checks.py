"""Validity, leakage, and contamination checks run on every prepared set.

Each check returns a list of problems (empty = pass) rather than raising, so
a build reports every failure at once.
"""

from pathlib import Path

import pandas as pd

from . import config
from .series import SplitSeries


def check_values(s: SplitSeries) -> list[str]:
    """No missing values, and strictly positive values everywhere, so that
    percentage-error metrics (sMAPE, MAPE) are well defined."""
    problems = []
    for part, df in (("train", s.train), ("heldout", s.heldout)):
        if df["value"].isna().any():
            problems.append(f"{s.series_id}: {part} has {int(df['value'].isna().sum())} missing values")
        elif (df["value"] <= 0).any():
            problems.append(f"{s.series_id}: {part} has non-positive values")
    return problems


def check_split(s: SplitSeries) -> list[str]:
    """The held-out part is exactly the horizon, comes strictly after train,
    shares no dates with it, and continues it without a gap."""
    problems = []
    if len(s.heldout) != s.horizon:
        problems.append(f"{s.series_id}: heldout has {len(s.heldout)} rows, expected horizon {s.horizon}")
    if len(s.train) < 2:
        problems.append(f"{s.series_id}: train has fewer than 2 rows")
        return problems
    if set(s.train["date"]) & set(s.heldout["date"]):
        problems.append(f"{s.series_id}: train and heldout share dates")
    if s.train["date"].max() >= s.heldout["date"].min():
        problems.append(f"{s.series_id}: heldout does not start after train ends")
    for part, df in (("train", s.train), ("heldout", s.heldout)):
        if not df["date"].is_monotonic_increasing or df["date"].duplicated().any():
            problems.append(f"{s.series_id}: {part} dates are not strictly increasing")
    full = pd.concat([s.train["date"], s.heldout["date"]], ignore_index=True)
    if len(full) > 2 and pd.infer_freq(full) is None:
        problems.append(f"{s.series_id}: train+heldout dates are not a regular series (gap or irregular spacing)")
    return problems


def check_contamination(s: SplitSeries) -> list[str]:
    """Contamination-control series must have their whole test window on or
    after CONTAMINATION_TEST_START."""
    if s.contamination_control and s.heldout["date"].min() < config.CONTAMINATION_TEST_START:
        return [(f"{s.series_id}: test starts {s.heldout['date'].min().date()}, before the contamination "
                 f"cutoff {config.CONTAMINATION_TEST_START.date()}")]
    return []


def check_written(set_dir: Path, series: list[SplitSeries]) -> list[str]:
    """On disk: train/ and heldout/ are separate, non-nested directories, and
    no held-out date appears in any train CSV."""
    problems = []
    train_dir, heldout_dir = (set_dir / "train").resolve(), (set_dir / "heldout").resolve()
    if train_dir in heldout_dir.parents or heldout_dir in train_dir.parents or train_dir == heldout_dir:
        problems.append("train/ and heldout/ directories overlap")
    for s in series:
        train = pd.read_csv(train_dir / f"{s.series_id}.csv", parse_dates=["date"])
        heldout = pd.read_csv(heldout_dir / f"{s.series_id}.csv", parse_dates=["date"])
        if set(train["date"]) & set(heldout["date"]):
            problems.append(f"{s.series_id}: written train CSV contains held-out dates")
        if len(train) != len(s.train) or len(heldout) != len(s.heldout):
            problems.append(f"{s.series_id}: written CSV row counts don't match")
    return problems


def check_series(s: SplitSeries) -> list[str]:
    return check_values(s) + check_split(s) + check_contamination(s)
