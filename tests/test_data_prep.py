import pandas as pd

from omen.data_prep import generate_synthetic_series, load_series


def test_generate_synthetic_series_shape():
    df = generate_synthetic_series(n_days=100)
    assert len(df) == 100
    assert list(df.columns) == ["date", "value"]
    assert df["value"].isna().sum() == 0


def test_generate_synthetic_series_is_deterministic_given_seed():
    df1 = generate_synthetic_series(n_days=50, seed=7)
    df2 = generate_synthetic_series(n_days=50, seed=7)
    pd.testing.assert_frame_equal(df1, df2)


def test_load_series_from_csv(tmp_path):
    df = generate_synthetic_series(n_days=30)
    csv_path = tmp_path / "series.csv"
    df.to_csv(csv_path, index=False)

    loaded = load_series(str(csv_path))
    assert len(loaded) == 30
    assert pd.api.types.is_datetime64_any_dtype(loaded["date"])
