import numpy as np
import pandas as pd
import pytest

pytest.importorskip("statsmodels")

from omen.data_prep import generate_synthetic_series
from omen.analyst.analysis_tools import (
    basic_stats,
    check_stationarity,
    seasonal_decomposition_summary,
    detect_seasonality_period,
    acf_pacf_summary,
    detect_anomalies_zscore,
    detect_anomalies_robust_zscore,
    detect_changepoints,
)


@pytest.fixture
def sample_df():
    return generate_synthetic_series(n_days=200)


def test_basic_stats(sample_df):
    result = basic_stats(sample_df)
    assert result["n_observations"] == 200
    assert result["n_missing_values"] == 0


def test_basic_stats_mean_ci_brackets_the_mean(sample_df):
    result = basic_stats(sample_df)
    assert result["mean_ci_lower"] < result["mean"] < result["mean_ci_upper"]
    assert result["confidence_level"] == 0.95


def test_basic_stats_mean_ci_widens_with_lower_confidence_level(sample_df):
    narrow = basic_stats(sample_df, confidence_level=0.80)
    wide = basic_stats(sample_df, confidence_level=0.99)
    narrow_width = narrow["mean_ci_upper"] - narrow["mean_ci_lower"]
    wide_width = wide["mean_ci_upper"] - wide["mean_ci_lower"]
    assert wide_width > narrow_width


def test_basic_stats_mean_ci_is_none_for_constant_series():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=10, freq="D"), "value": [5.0] * 10})
    result = basic_stats(df)
    assert result["std"] == 0
    assert result["mean_ci_lower"] is None
    assert result["mean_ci_upper"] is None


def test_check_stationarity_returns_expected_keys(sample_df):
    result = check_stationarity(sample_df)
    assert "adf_statistic" in result
    assert "adf_p_value" in result
    assert isinstance(result["adf_is_likely_stationary"], bool)
    assert "mean_reversion_lambda" in result
    assert "mean_reversion_lambda_ci_lower" in result
    assert "mean_reversion_lambda_ci_upper" in result
    assert "mean_reversion_half_life_periods" in result
    assert "mean_reversion_half_life_ci_lower" in result
    assert "mean_reversion_half_life_ci_upper" in result
    assert "kpss_statistic" in result
    assert "kpss_p_value" in result
    assert isinstance(result["kpss_is_likely_stationary"], bool)
    assert "kpss_effect_size" in result
    assert "kpss_critical_value_5pct" in result


def _mean_reverting_ar1_df(seed: int = 0, n: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.7 * y[t - 1] + rng.normal(0, 1.0)  # AR(1), strongly mean-reverting
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n, freq="D"), "value": y})


def _random_walk_df(seed: int = 3, n: int = 500) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    y = np.cumsum(rng.normal(0, 1.0, size=n))  # random walk: no true mean reversion
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n, freq="D"), "value": y})


def test_check_stationarity_reports_finite_half_life_for_mean_reverting_series():
    result = check_stationarity(_mean_reverting_ar1_df())
    assert result["mean_reversion_lambda"] < 0
    assert result["mean_reversion_half_life_periods"] is not None
    assert result["mean_reversion_half_life_periods"] > 0

    # lambda's CI should bracket its own point estimate.
    assert result["mean_reversion_lambda_ci_lower"] <= result["mean_reversion_lambda"]
    assert result["mean_reversion_lambda"] <= result["mean_reversion_lambda_ci_upper"]

    # Strong, clearly-mean-reverting AR(1) data: the whole lambda CI should
    # be negative, so half-life's upper bound should be finite (not None).
    assert result["mean_reversion_lambda_ci_upper"] < 0
    assert result["mean_reversion_half_life_ci_lower"] is not None
    assert result["mean_reversion_half_life_ci_upper"] is not None
    # half-life is an INCREASING function of lambda (more negative = faster
    # reversion = shorter half-life), so lower <= point estimate <= upper.
    assert (
        result["mean_reversion_half_life_ci_lower"]
        <= result["mean_reversion_half_life_periods"]
        <= result["mean_reversion_half_life_ci_upper"]
    )


def test_check_stationarity_reports_weak_reversion_for_a_pure_random_walk():
    n = 500
    result = check_stationarity(_random_walk_df(n=n))
    # Don't assert mean_reversion_lambda >= 0 here: under a true unit root, the
    # OLS lambda estimate is well-known to skew slightly negative in finite
    # samples (the reason ADF needs its own non-standard critical values
    # rather than a plain t-test) -- it's not reliably non-negative even when
    # there's truly no reversion. What should hold instead: the formal ADF
    # verdict says non-stationary, and if a half-life comes out at all, it's
    # long enough to be practically meaningless, not a fast, useful reversion.
    assert result["adf_is_likely_stationary"] is False
    assert (
        result["mean_reversion_half_life_periods"] is None
        or result["mean_reversion_half_life_periods"] > n / 2
    )


def test_check_stationarity_half_life_ci_upper_is_unbounded_when_lambda_ci_crosses_zero():
    result = check_stationarity(_random_walk_df())
    # On this random walk, lambda's point estimate is (weakly) negative but
    # its CI reaches into non-negative territory -- the data can't rule out
    # arbitrarily slow reversion, so half-life's upper bound must be None
    # (unbounded), not some large-but-finite number.
    assert result["mean_reversion_lambda_ci_upper"] >= 0
    assert result["mean_reversion_half_life_ci_upper"] is None
    assert result["mean_reversion_half_life_ci_lower"] is not None
    assert "unbounded" in result["interpretation"]


def test_check_stationarity_kpss_agrees_with_adf_on_mean_reverting_series():
    result = check_stationarity(_mean_reverting_ar1_df())
    assert result["adf_is_likely_stationary"] is True
    assert result["kpss_is_likely_stationary"] is True
    assert result["kpss_effect_size"] < 1  # comfortably under its 5% critical value
    assert "agree" in result["interpretation"]


def test_check_stationarity_kpss_agrees_with_adf_on_a_random_walk():
    result = check_stationarity(_random_walk_df())
    assert result["adf_is_likely_stationary"] is False
    assert result["kpss_is_likely_stationary"] is False
    assert result["kpss_effect_size"] > 1  # exceeds its 5% critical value
    assert "agree" in result["interpretation"]


def test_check_stationarity_kpss_effect_size_survives_p_value_clipping():
    # KPSS's own p-value is clipped at table boundaries (0.01/0.10); the
    # effect size should still distinguish magnitude past that clip.
    result = check_stationarity(_random_walk_df())
    assert result["kpss_p_value"] == 0.01  # clipped at the table's edge
    assert result["kpss_effect_size"] > 1  # but the effect size isn't clipped


def test_check_stationarity_kpss_regression_param_is_threaded_through():
    df = _mean_reverting_ar1_df()
    result_c = check_stationarity(df, kpss_regression="c")
    result_ct = check_stationarity(df, kpss_regression="ct")
    assert result_c["kpss_regression"] == "c"
    assert result_ct["kpss_regression"] == "ct"
    # "c" and "ct" fit different regressions internally, so the raw
    # statistic differs even on the same series.
    assert result_c["kpss_statistic"] != result_ct["kpss_statistic"]


def test_seasonal_decomposition_summary(sample_df):
    result = seasonal_decomposition_summary(sample_df, period=7)
    assert 0 <= result["trend_strength"] <= 1
    assert 0 <= result["seasonal_strength"] <= 1


def test_detect_seasonality_period_finds_weekly_seasonality():
    df = generate_synthetic_series(n_days=300)  # trend + weekly + yearly seasonality
    result = detect_seasonality_period(df)

    periods = [c["period"] for c in result["top_candidate_periods"]]
    assert any(abs(p - 7) < 0.5 for p in periods)
    # The strongest in-range candidate should be the weekly period, and
    # it should carry a large share of total periodogram power.
    top = result["top_candidate_periods"][0]
    assert abs(top["period"] - 7) < 0.5
    assert top["relative_power"] > 0.1


def test_detect_seasonality_period_flags_dominant_period_out_of_range():
    # The series' own trend dominates the raw periodogram at the lowest
    # frequency (period ~= series length), which sits outside the
    # reported [min_period, max_period] range by construction.
    df = generate_synthetic_series(n_days=300)
    result = detect_seasonality_period(df, min_period=2, max_period=150)
    assert result["dominant_period_in_reported_range"] is False
    assert result["dominant_period"] > 150


def test_detect_seasonality_period_handles_constant_series():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=20, freq="D"), "value": [5.0] * 20})
    result = detect_seasonality_period(df)
    assert "error" in result


def test_detect_seasonality_period_handles_too_short_series():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5, freq="D"), "value": [1, 2, 3, 4, 5]})
    result = detect_seasonality_period(df)
    assert "error" in result


def test_acf_pacf_summary(sample_df):
    result = acf_pacf_summary(sample_df, n_lags=14)
    assert result["n_lags_checked"] == 14
    assert result["significance_alpha"] == 0.05


def test_acf_pacf_summary_significant_lags_have_per_lag_ci_and_effect_size_sorted_strongest_first():
    df = generate_synthetic_series(n_days=300)  # strong weekly seasonality vs. noise
    result = acf_pacf_summary(df, n_lags=21)

    lags = result["significant_acf_lags"]
    assert len(lags) > 0
    for entry in lags:
        assert set(entry) == {"lag", "acf", "ci_lower", "ci_upper", "effect_size"}
        half_width = (entry["ci_upper"] - entry["ci_lower"]) / 2.0
        # Recomputed from already-rounded fields as a sanity check only --
        # the code itself computes effect_size once from full-precision
        # inputs, so this can differ in the last digit from double-rounding.
        assert entry["effect_size"] == pytest.approx(abs(entry["acf"]) / half_width, abs=1e-2)
        assert entry["effect_size"] > 1  # by definition of "significant" here
        # 0 must fall outside the CI for a flagged (significant) lag.
        assert not (entry["ci_lower"] <= 0 <= entry["ci_upper"])

    effect_sizes = [entry["effect_size"] for entry in lags]
    assert effect_sizes == sorted(effect_sizes, reverse=True)

    # Lag 1's Bartlett standard error is the tightest of any lag (no prior
    # lags inflate its variance), so on data with strong short-lag
    # autocorrelation, lag 1 should be the single strongest entry -- this
    # is also the concrete case where the OLD uniform 1.96/sqrt(n)
    # threshold gave a different (wrong) answer, ranking lag 7 first.
    assert lags[0]["lag"] == 1


def test_detect_anomalies_zscore(sample_df):
    result = detect_anomalies_zscore(sample_df, z_threshold=3.0)
    assert "n_anomalies_flagged" in result
    assert "anomalies" in result
    assert "max_abs_z_score" in result


def test_detect_anomalies_zscore_reports_z_score_sorted_most_extreme_first():
    df = generate_synthetic_series(n_days=300)
    df.loc[100, "value"] += 500  # huge spike
    df.loc[150, "value"] += 60  # smaller, still-flagged bump

    result = detect_anomalies_zscore(df, z_threshold=3.0)
    assert result["n_anomalies_flagged"] >= 1
    assert result["max_abs_z_score"] == max(abs(a["z_score"]) for a in result["anomalies"])

    for anomaly in result["anomalies"]:
        assert set(anomaly) == {"date", "value", "z_score"}

    abs_z_scores = [abs(a["z_score"]) for a in result["anomalies"]]
    assert abs_z_scores == sorted(abs_z_scores, reverse=True)
    assert abs_z_scores[0] == result["max_abs_z_score"]


def test_detect_anomalies_zscore_handles_no_anomalies():
    df = generate_synthetic_series(n_days=100, noise_std=0.001, weekly_amplitude=0, yearly_amplitude=0)
    result = detect_anomalies_zscore(df, z_threshold=8.0)
    assert result["n_anomalies_flagged"] == 0
    assert result["anomalies"] == []
    assert result["max_abs_z_score"] is None


def test_detect_anomalies_robust_zscore_fixes_self_dilution():
    # detect_anomalies_zscore's rolling std is inflated by the very spike
    # it's trying to measure (confirmed during development: a +500 spike
    # only scored z=3.44, not something far higher). The robust
    # (median/MAD) version shouldn't have that self-dilution problem.
    df = generate_synthetic_series(n_days=300)
    df.loc[100, "value"] += 500

    non_robust = detect_anomalies_zscore(df, z_threshold=3.0)
    robust = detect_anomalies_robust_zscore(df, z_threshold=3.5)

    assert non_robust["n_anomalies_flagged"] >= 1
    assert robust["n_anomalies_flagged"] >= 1
    assert robust["max_abs_modified_z_score"] > non_robust["max_abs_z_score"] * 2

    for anomaly in robust["anomalies"]:
        assert set(anomaly) == {"date", "value", "modified_z_score"}


def test_detect_anomalies_robust_zscore_sorted_most_extreme_first():
    df = generate_synthetic_series(n_days=300)
    df.loc[100, "value"] += 500
    df.loc[150, "value"] += 150  # smaller than the first spike, but still flagged

    result = detect_anomalies_robust_zscore(df, z_threshold=3.5)
    assert result["n_anomalies_flagged"] >= 2
    abs_scores = [abs(a["modified_z_score"]) for a in result["anomalies"]]
    assert abs_scores == sorted(abs_scores, reverse=True)
    assert abs_scores[0] == result["max_abs_modified_z_score"]


def test_detect_anomalies_robust_zscore_handles_no_anomalies():
    df = generate_synthetic_series(n_days=100, noise_std=0.001, weekly_amplitude=0, yearly_amplitude=0)
    result = detect_anomalies_robust_zscore(df, z_threshold=8.0)
    assert result["n_anomalies_flagged"] == 0
    assert result["anomalies"] == []
    assert result["max_abs_modified_z_score"] is None


def _level_shift_df(seed: int = 0, n: int = 200, shift_at: int = 100, shift_size: float = 5.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    y = rng.normal(0, 1.0, size=n)
    y[shift_at:] += shift_size
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n, freq="D"), "value": y})


def test_detect_changepoints_finds_a_clean_level_shift():
    df = _level_shift_df()
    result = detect_changepoints(df)

    assert result["n_changepoints_found"] == 1
    cp = result["changepoints"][0]
    assert cp["index"] == 100
    assert cp["mean_after"] - cp["mean_before"] == pytest.approx(5.0, abs=0.5)
    assert cp["cohens_d_effect_size"] > 1  # a 5-sigma shift is a huge effect
    assert cp["p_value"] < 0.05


def test_detect_changepoints_finds_no_break_in_pure_noise():
    rng = np.random.default_rng(1)
    n = 200
    df = pd.DataFrame(
        {"date": pd.date_range("2024-01-01", periods=n, freq="D"), "value": rng.normal(0, 1.0, size=n)}
    )
    result = detect_changepoints(df)
    assert result["n_changepoints_found"] == 0
    assert result["changepoints"] == []


def test_detect_changepoints_finds_two_breaks():
    rng = np.random.default_rng(2)
    n = 300
    y = rng.normal(0, 1.0, size=n)
    y[100:200] += 6.0
    y[200:] -= 3.0
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n, freq="D"), "value": y})

    result = detect_changepoints(df)
    assert result["n_changepoints_found"] == 2
    indices = [cp["index"] for cp in result["changepoints"]]
    assert indices == sorted(indices)  # reported in chronological order
    assert indices[0] == 100
    assert indices[1] == 200


def test_detect_changepoints_is_deterministic_given_the_same_seed():
    df = _level_shift_df()
    result_a = detect_changepoints(df, seed=42)
    result_b = detect_changepoints(df, seed=42)
    assert result_a == result_b


def test_detect_changepoints_handles_too_short_series():
    df = pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5, freq="D"), "value": [1, 2, 3, 4, 5]})
    result = detect_changepoints(df, min_segment_size=10)
    assert "error" in result
