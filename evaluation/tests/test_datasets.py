"""Offline tests for the Eval 02 dataset pipeline (no network access)."""

import json

import numpy as np
import pandas as pd
import pytest
from omen_eval import checks, config, fresh, m4, prepare
from omen_eval.series import SplitSeries, split_last


def _info(sid: str, starting_date: str, category: str = "Macro", freq: int = 1) -> pd.Series:
    return pd.Series({"M4id": sid, "category": category, "Frequency": freq, "StartingDate": starting_date})


def _daily(start: str, n: int, value: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.date_range(start, periods=n, freq="D"), "value": np.full(n, value)})


# --- M4 date reconstruction ---------------------------------------------------

def test_resolve_start_prefers_20yy_when_series_ends_by_2018():
    assert m4.resolve_start("03-01-07 12:00", n_total=100, kind="D") == pd.Timestamp("2007-01-03")


def test_resolve_start_falls_back_to_19yy_when_20yy_would_end_after_2018():
    # 2079 is impossible; 1979 + 100 days is fine.
    assert m4.resolve_start("01-01-79 12:00", n_total=100, kind="D") == pd.Timestamp("1979-01-01")
    # 2015 + 10,000 days runs past 2018, so the series must start in 1915.
    assert m4.resolve_start("01-01-15 12:00", n_total=10_000, kind="D") == pd.Timestamp("1915-01-01")


def test_resolve_start_normalizes_monthly_to_month_start():
    assert m4.resolve_start("15-06-76 12:00", n_total=50, kind="MS") == pd.Timestamp("1976-06-01")


def test_build_series_weekly_dates_are_regular_and_split_at_horizon():
    train, test = np.arange(1.0, 41.0), np.arange(41.0, 54.0)
    s = m4.build_series("W1", train, test, _info("W1", "08-01-75 12:00"), "weekly")
    assert s.series_id == "m4-W1" and s.horizon == 13
    assert len(s.train) == 40 and len(s.heldout) == 13
    full = pd.concat([s.train["date"], s.heldout["date"]])
    assert pd.infer_freq(full).startswith("W-")
    assert checks.check_series(s) == []


def test_build_series_rejects_wrong_test_length():
    with pytest.raises(ValueError, match="horizon"):
        m4.build_series("D1", np.ones(50), np.ones(5), _info("D1", "03-01-94 12:00"), "daily")


def test_read_wide_drops_padding(tmp_path):
    path = tmp_path / "Daily-train.csv"
    path.write_text('"V1","V2","V3","V4"\n"D1","1","2","3"\n"D2","4","5",\n')
    out = m4.read_wide(path)
    assert out["D1"].tolist() == [1.0, 2.0, 3.0]
    assert out["D2"].tolist() == [4.0, 5.0]


def test_sample_ids_is_seeded_and_prefix_stable():
    info = pd.DataFrame({"M4id": [f"D{i}" for i in range(1, 101)], "SP": "Daily"})
    small, large = m4.sample_ids(info, "daily", 5), m4.sample_ids(info, "daily", 20)
    assert small == m4.sample_ids(info, "daily", 5)  # deterministic
    assert large[:5] == small  # pilot is a subset (prefix) of the full set


# --- Fresh data parsing ---------------------------------------------------------

def test_parse_wikimedia_and_open_meteo():
    wiki = fresh.parse_wikimedia({"items": [{"timestamp": "2026100100", "views": 5},
                                            {"timestamp": "2026100200", "views": 7}]})
    assert wiki["date"].tolist() == [pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-02")]
    assert wiki["value"].tolist() == [5.0, 7.0]
    meteo = fresh.parse_open_meteo({"daily": {"time": ["2026-10-01"], config.OPEN_METEO_VARIABLE: [27.5]}})
    assert meteo["value"].tolist() == [27.5]


def test_complete_daily_exposes_gaps_as_missing_values():
    df = _daily(config.FRESH_TRAIN_START.date().isoformat(), 30)
    df = df.drop(index=10)
    out = fresh.complete_daily(df)
    assert out["value"].isna().sum() > 0  # the dropped day, plus everything after the 30 days


def test_sample_keys_is_seeded_and_prefix_stable():
    keys = config.WIKIMEDIA_ARTICLES
    assert fresh.sample_keys(keys, 3, "wikimedia") == fresh.sample_keys(keys, 15, "wikimedia")[:3]


# --- Checks -----------------------------------------------------------------------

def _split(df: pd.DataFrame, horizon: int = 14, contamination: bool = False) -> SplitSeries:
    return split_last("x", df, horizon, source="test", frequency="daily", license="n/a",
                      contamination_control=contamination)


def test_clean_series_passes_all_checks():
    assert checks.check_series(_split(_daily("2026-01-01", 200), contamination=True)) == []


def test_contamination_check_rejects_test_window_before_cutoff():
    s = _split(_daily("2025-01-01", 200), contamination=True)  # test ends mid-2025
    assert any("contamination cutoff" in p for p in checks.check_contamination(s))


def test_value_checks_reject_missing_and_non_positive():
    df = _daily("2026-01-01", 200)
    df.loc[5, "value"] = np.nan
    assert any("missing" in p for p in checks.check_values(_split(df)))
    df = _daily("2026-01-01", 200)
    df.loc[5, "value"] = 0.0
    assert any("non-positive" in p for p in checks.check_values(_split(df)))


def test_split_check_rejects_overlap_and_gaps():
    s = _split(_daily("2026-01-01", 200))
    s.heldout = pd.concat([s.train.tail(1), s.heldout.iloc[1:]], ignore_index=True)  # overlap
    assert any("share dates" in p for p in checks.check_split(s))
    gappy = _daily("2026-01-01", 200).drop(index=100).reset_index(drop=True)
    assert any("regular" in p for p in checks.check_split(_split(gappy)))


def test_write_set_writes_separate_dirs_and_manifest(tmp_path):
    series = [_split(_daily("2026-01-01", 200), contamination=True)]
    manifest = prepare.write_set("unit", series, [], out_root=tmp_path / "prepared",
                                 manifest_dir=tmp_path / "manifests")
    set_dir = tmp_path / "prepared" / "unit"
    train = pd.read_csv(set_dir / "train" / "x.csv")
    heldout = pd.read_csv(set_dir / "heldout" / "x.csv")
    assert list(train.columns) == ["date", "value"] and len(train) == 186 and len(heldout) == 14
    assert manifest["checks"] == "passed" and manifest["series"][0]["n_test"] == 14
    assert json.loads((tmp_path / "manifests" / "unit.json").read_text()) == manifest


def test_write_set_raises_on_failed_check(tmp_path):
    series = [_split(_daily("2025-01-01", 200), contamination=True)]
    with pytest.raises(RuntimeError, match="contamination cutoff"):
        prepare.write_set("unit", series, [], out_root=tmp_path / "prepared", manifest_dir=tmp_path / "m")
