"""The split-series record shared by every data source."""

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SplitSeries:
    """One series, already split into the agent-visible train part and the
    held-out test part. Both frames have columns ['date', 'value']."""

    series_id: str
    source: str  # "m4", "wikimedia", "open_meteo"
    frequency: str  # "daily", "weekly", "monthly"
    horizon: int
    train: pd.DataFrame
    heldout: pd.DataFrame
    license: str
    contamination_control: bool = False
    metadata: dict = field(default_factory=dict)


def split_last(series_id: str, df: pd.DataFrame, horizon: int, **kwargs) -> SplitSeries:
    """Split a full ['date', 'value'] frame into train and the last `horizon` rows."""
    df = df.sort_values("date").reset_index(drop=True)
    return SplitSeries(
        series_id=series_id,
        horizon=horizon,
        train=df.iloc[:-horizon].reset_index(drop=True),
        heldout=df.iloc[-horizon:].reset_index(drop=True),
        **kwargs,
    )
