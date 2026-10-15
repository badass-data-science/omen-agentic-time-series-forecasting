"""M4 competition data (Makridakis, Spiliotis & Assimakopoulos, 2020, IJF).

The M4-methods repository has no license file, so the raw files are never
committed: they are downloaded into evaluation/data/raw/m4/ and verified
against SHA-256 checksums recorded on first download.

M4 uses its own train/test split (the test file holds exactly the horizon),
which is kept as-is. M4-info.csv gives each series' start as "dd-mm-yy HH:MM";
dates are rebuilt from it (see `resolve_start`).
"""

import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .series import SplitSeries

M4_LICENSE = "No license file in Mcompetitions/M4-methods; used for research with citation, not redistributed"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_files(prefixes: list[str], raw_dir: Path = config.RAW_DIR / "m4",
                 checksum_file: Path = config.MANIFEST_DIR / "m4_checksums.json") -> dict[str, Path]:
    """Download the needed M4 files if missing, and verify their checksums.

    Checksums are recorded the first time a file is seen and verified on
    every later run, so a silently changed upstream file fails loudly.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    rel_paths = ["M4-info.csv"] + [f"{split}/{p}-{split.lower()}.csv" for p in prefixes for split in ("Train", "Test")]
    checksums = json.loads(checksum_file.read_text()) if checksum_file.exists() else {}
    paths = {}
    for rel in rel_paths:
        dest = raw_dir / rel.replace("/", "_")
        if not dest.exists():
            req = urllib.request.Request(f"{config.M4_BASE_URL}/{rel}", headers={"User-Agent": config.USER_AGENT})
            with urllib.request.urlopen(req, timeout=300) as resp:
                dest.write_bytes(resp.read())
        digest = _sha256(dest)
        if rel in checksums and checksums[rel] != digest:
            raise RuntimeError(f"M4 file {rel} changed: expected sha256 {checksums[rel]}, got {digest}")
        checksums[rel] = digest
        paths[rel] = dest
    checksum_file.parent.mkdir(parents=True, exist_ok=True)
    checksum_file.write_text(json.dumps(dict(sorted(checksums.items())), indent=2) + "\n")
    return paths


def read_wide(path: Path, ids: set[str] | None = None) -> dict[str, np.ndarray]:
    """Read an M4 wide CSV (V1 = id, V2.. = values, NaN-padded) into id -> values."""
    df = pd.read_csv(path, index_col=0)
    if ids is not None:
        df = df.loc[df.index.isin(ids)]
    return {sid: row.dropna().to_numpy(dtype=float) for sid, row in df.iterrows()}


def _offset(kind: str, start: pd.Timestamp) -> pd.DateOffset:
    if kind == "W":
        return pd.offsets.Week(weekday=start.weekday())
    if kind == "MS":
        return pd.offsets.MonthBegin()
    return pd.offsets.Day()


def resolve_start(starting_date: str, n_total: int, kind: str) -> pd.Timestamp:
    """Turn M4-info's "dd-mm-yy HH:MM" into a start date.

    Two-digit years are ambiguous, so the century is chosen as the latest one
    (20yy, else 19yy) whose series would end no later than 2018-12-31, when
    M4's data were collected. Monthly starts are normalized to the 1st of the
    month so the dates form a regular month-start index.
    """
    day, month, yy = (int(x) for x in starting_date.split()[0].split("-"))
    start = pd.Timestamp(1900 + yy, month, day)
    for century in (2000, 1900):
        candidate = pd.Timestamp(century + yy, month, day)
        if kind == "MS":
            candidate = candidate.replace(day=1)
        end = candidate + (n_total - 1) * _offset(kind, candidate)
        if end <= config.M4_LATEST_PLAUSIBLE_END:
            start = candidate
            break
    else:
        if kind == "MS":
            start = start.replace(day=1)
    return start


def build_series(sid: str, train_values: np.ndarray, test_values: np.ndarray, info: pd.Series,
                 frequency: str) -> SplitSeries:
    """Build a SplitSeries for one M4 id from its train/test values and M4-info row."""
    _prefix, horizon, kind = config.M4_FREQUENCIES[frequency]
    if len(test_values) != horizon:
        raise ValueError(f"{sid}: test has {len(test_values)} values, expected horizon {horizon}")
    n_total = len(train_values) + horizon
    start = resolve_start(info["StartingDate"], n_total, kind)
    dates = pd.date_range(start, periods=n_total, freq=_offset(kind, start))
    values = np.concatenate([train_values, test_values])
    full = pd.DataFrame({"date": dates, "value": values})
    return SplitSeries(
        series_id=f"m4-{sid}",
        source="m4",
        frequency=frequency,
        horizon=horizon,
        train=full.iloc[: len(train_values)].reset_index(drop=True),
        heldout=full.iloc[len(train_values):].reset_index(drop=True),
        license=M4_LICENSE,
        metadata={"m4_id": sid, "m4_category": info["category"], "m4_seasonal_period": int(info["Frequency"]),
                  "m4_starting_date": info["StartingDate"]},
    )


def sample_ids(info: pd.DataFrame, frequency: str, n: int, seed: int = config.SEED) -> list[str]:
    """Seeded sample of n M4 ids for one frequency. Uses a fixed permutation
    and takes the first n, so a smaller set is always a prefix of a larger one
    (the pilot set is a subset of the full set)."""
    prefix = config.M4_FREQUENCIES[frequency][0]
    ids = sorted(info.loc[info["SP"] == prefix, "M4id"])
    freq_index = list(config.M4_FREQUENCIES).index(frequency)
    order = np.random.default_rng([seed, freq_index]).permutation(len(ids))
    return [ids[i] for i in order[:n]]


def load(frequency: str, n: int, seed: int = config.SEED) -> list[SplitSeries]:
    """Download (if needed), sample, and build n series of one M4 frequency."""
    prefix = config.M4_FREQUENCIES[frequency][0]
    paths = ensure_files([prefix])
    info = pd.read_csv(paths["M4-info.csv"])
    ids = sample_ids(info, frequency, n, seed)
    train = read_wide(paths[f"Train/{prefix}-train.csv"], set(ids))
    test = read_wide(paths[f"Test/{prefix}-test.csv"], set(ids))
    info_by_id = info.set_index("M4id")
    return [build_series(sid, train[sid], test[sid], info_by_id.loc[sid], frequency) for sid in ids]
