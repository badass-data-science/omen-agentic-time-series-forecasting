"""Fresh daily series for contamination control: Wikimedia pageviews and
Open-Meteo daily mean temperature.

Raw API responses are frozen as JSON snapshots under
evaluation/data/snapshots/ and committed. Builds always read the snapshot,
so the dataset doesn't drift when an API revises past values (Open-Meteo's
recent archive values are preliminary and get replaced later). Pass
refresh=True to re-fetch deliberately; record that in the Eval 02 record.
"""

import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .series import SplitSeries, split_last


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())


def _snapshot(path: Path, url: str, refresh: bool) -> dict:
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    data = _fetch_json(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "response": data}, separators=(",", ":")) + "\n")
    return {"url": url, "response": data}


def wikimedia_url(article: str) -> str:
    start = config.FRESH_TRAIN_START.strftime("%Y%m%d")
    end = config.FRESH_DATA_END.strftime("%Y%m%d")
    title = urllib.parse.quote(article, safe="")
    return ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
            f"en.wikipedia/all-access/user/{title}/daily/{start}00/{end}00")


def open_meteo_url(lat: float, lon: float) -> str:
    query = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": config.FRESH_TRAIN_START.date().isoformat(),
        "end_date": config.FRESH_DATA_END.date().isoformat(),
        "daily": config.OPEN_METEO_VARIABLE, "timezone": "auto",
    })
    return f"https://archive-api.open-meteo.com/v1/archive?{query}"


def parse_wikimedia(response: dict) -> pd.DataFrame:
    items = response.get("items", [])
    return pd.DataFrame({
        "date": pd.to_datetime([it["timestamp"][:8] for it in items], format="%Y%m%d"),
        "value": [float(it["views"]) for it in items],
    })


def parse_open_meteo(response: dict) -> pd.DataFrame:
    daily = response["daily"]
    return pd.DataFrame({
        "date": pd.to_datetime(daily["time"]),
        "value": np.asarray(daily[config.OPEN_METEO_VARIABLE], dtype=float),
    })


def complete_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Reindex to every day from FRESH_TRAIN_START to FRESH_DATA_END. Missing
    days become NaN, which the validity checks then reject (no imputation)."""
    full_index = pd.date_range(config.FRESH_TRAIN_START, config.FRESH_DATA_END, freq="D")
    out = df.set_index("date").reindex(full_index)
    out.index.name = "date"
    return out.reset_index()


def _build(series_id: str, df: pd.DataFrame, source: str, license_: str, metadata: dict) -> SplitSeries:
    return split_last(series_id, complete_daily(df), config.FRESH_HORIZON, source=source, frequency="daily",
                      license=license_, contamination_control=True, metadata=metadata)


# Fixed per-source random streams (distinct from M4's per-frequency streams 0-2).
_SOURCE_STREAM = {"wikimedia": 101, "open_meteo": 102}


def sample_keys(keys: list[str], n: int, source: str, seed: int = config.SEED) -> list[str]:
    """Seeded first-n of a fixed permutation, so smaller sets are prefixes of larger ones."""
    ordered = sorted(keys)
    order = np.random.default_rng([seed, _SOURCE_STREAM[source]]).permutation(len(ordered))
    return [ordered[i] for i in order[:n]]


def load_wikimedia(n: int, refresh: bool = False, seed: int = config.SEED) -> list[SplitSeries]:
    out = []
    for article in sample_keys(config.WIKIMEDIA_ARTICLES, n, "wikimedia", seed):
        url = wikimedia_url(article)
        snap = _snapshot(config.SNAPSHOT_DIR / "wikimedia" / f"{article}.json", url, refresh)
        out.append(_build(f"wiki-{article}", parse_wikimedia(snap["response"]), "wikimedia",
                          config.WIKIMEDIA_LICENSE, {"article": article, "project": "en.wikipedia",
                                                     "agent": "user", "url": snap["url"]}))
    return out


def load_open_meteo(n: int, refresh: bool = False, seed: int = config.SEED) -> list[SplitSeries]:
    out = []
    for city in sample_keys(list(config.OPEN_METEO_CITIES), n, "open_meteo", seed):
        lat, lon = config.OPEN_METEO_CITIES[city]
        url = open_meteo_url(lat, lon)
        snap = _snapshot(config.SNAPSHOT_DIR / "open_meteo" / f"{city}.json", url, refresh)
        out.append(_build(f"meteo-{city}", parse_open_meteo(snap["response"]), "open_meteo",
                          config.OPEN_METEO_LICENSE, {"city": city, "latitude": lat, "longitude": lon,
                                                      "variable": config.OPEN_METEO_VARIABLE, "url": snap["url"]}))
    return out
