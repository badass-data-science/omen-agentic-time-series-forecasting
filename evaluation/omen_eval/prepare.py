"""Build a dataset set (pilot or full): sample, validate, write, manifest.

Layout written under evaluation/data/prepared/<set>/:
  train/<series_id>.csv     date,value: the ONLY directory an agent may see
  heldout/<series_id>.csv   date,value: test periods, for scoring only
  manifest.json             per-series metadata and file checksums

A copy of the manifest (no data values, just ids, ranges, and checksums) is
written to evaluation/data/manifests/<set>.json for committing.
"""

import hashlib
import json
from pathlib import Path

from . import checks, config, fresh, m4
from .series import SplitSeries


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(set_name: str, refresh_fresh: bool = False) -> tuple[list[SplitSeries], list[dict]]:
    """Collect a set's series, skipping (and recording) any that fail the
    value checks, taking further candidates in seeded order to refill."""
    spec = config.SETS[set_name]
    kept: list[SplitSeries] = []
    dropped: list[dict] = []

    def take(candidates: list[SplitSeries], n: int) -> None:
        got = 0
        for s in candidates:
            if got == n:
                break
            problems = checks.check_values(s)
            if problems:
                dropped.append({"series_id": s.series_id, "reasons": problems})
                continue
            kept.append(s)
            got += 1
        if got < n:
            raise RuntimeError(f"only {got} valid series available, {n} requested")

    # Over-sample candidates so a few drops can be refilled in seeded order.
    for frequency in config.M4_FREQUENCIES:
        n = spec["m4_per_frequency"]
        take(m4.load(frequency, n + 10), n)
    take(fresh.load_wikimedia(len(config.WIKIMEDIA_ARTICLES), refresh_fresh), spec["wikimedia"])
    take(fresh.load_open_meteo(len(config.OPEN_METEO_CITIES), refresh_fresh), spec["open_meteo"])
    return kept, dropped


def write_set(set_name: str, series: list[SplitSeries], dropped: list[dict],
              out_root: Path = config.PREPARED_DIR, manifest_dir: Path = config.MANIFEST_DIR) -> dict:
    """Write train/heldout CSVs and the manifest, then run every check.
    Raises if any check fails."""
    set_dir = out_root / set_name
    for sub in ("train", "heldout"):
        (set_dir / sub).mkdir(parents=True, exist_ok=True)
        for old in (set_dir / sub).glob("*.csv"):
            old.unlink()

    problems: list[str] = []
    entries = []
    for s in series:
        problems += checks.check_series(s)
        paths = {}
        for part, df in (("train", s.train), ("heldout", s.heldout)):
            path = set_dir / part / f"{s.series_id}.csv"
            df.assign(date=df["date"].dt.strftime("%Y-%m-%d")).to_csv(path, index=False)
            paths[part] = path
        entries.append({
            "series_id": s.series_id, "source": s.source, "frequency": s.frequency, "horizon": s.horizon,
            "contamination_control": s.contamination_control, "license": s.license,
            "train_start": s.train["date"].min().date().isoformat(),
            "train_end": s.train["date"].max().date().isoformat(), "n_train": len(s.train),
            "test_start": s.heldout["date"].min().date().isoformat(),
            "test_end": s.heldout["date"].max().date().isoformat(), "n_test": len(s.heldout),
            "train_sha256": _sha256(paths["train"]), "heldout_sha256": _sha256(paths["heldout"]),
            **({"metadata": s.metadata} if s.metadata else {}),
        })
    problems += checks.check_written(set_dir, series)
    if problems:
        raise RuntimeError("dataset checks failed:\n  " + "\n  ".join(problems))

    manifest = {
        "set": set_name, "seed": config.SEED, "spec": config.SETS.get(set_name),
        "contamination_test_start": config.CONTAMINATION_TEST_START.date().isoformat(),
        "fresh_train_start": config.FRESH_TRAIN_START.date().isoformat(),
        "fresh_data_end": config.FRESH_DATA_END.date().isoformat(),
        "checks": "passed", "n_series": len(entries), "series": entries, "dropped": dropped,
    }
    text = json.dumps(manifest, indent=1) + "\n"
    (set_dir / "manifest.json").write_text(text)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / f"{set_name}.json").write_text(text)
    return manifest
