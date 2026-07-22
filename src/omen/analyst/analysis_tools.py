"""
analysis_tools.py

The "tools" available to the Layer-1 agent. Each function does one concrete,
well-scoped piece of time series diagnostics and returns a small JSON-safe
dict summary (not raw arrays) so it can cheaply be passed back into an LLM's
context window.

These are plain Python functions today. In agent.py we wrap them with
Claude's tool-use (function calling) so the model decides which to call,
in what order, and how to interpret the results.
"""

import json
import warnings
from typing import Callable, Optional

import numpy as np
import pandas as pd
from scipy.signal import periodogram
from scipy.stats import t as _t_dist
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant
from statsmodels.tsa.stattools import adfuller, acf, kpss, pacf
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tools.sm_exceptions import InterpolationWarning


def basic_stats(df: pd.DataFrame, confidence_level: float = 0.95) -> dict:
    """Summary stats: length, date range, missing values, basic distribution.

    Also reports a confidence interval for the mean (Student's t, since
    sample sizes here can be small enough that the normal approximation
    isn't a safe substitute) -- a bare mean with no uncertainty band
    invites reading small differences (across series, or across cuts of
    the same series) as more meaningful than the sample size supports.
    """
    values = df["value"]
    n_non_missing = int(values.count())  # excludes NaNs, unlike len(df)
    mean = float(values.mean())
    std = float(values.std())

    mean_ci_lower = mean_ci_upper = None
    if n_non_missing > 1 and std > 0:
        standard_error = std / np.sqrt(n_non_missing)
        t_crit = float(_t_dist.ppf(1 - (1 - confidence_level) / 2, df=n_non_missing - 1))
        margin = t_crit * standard_error
        mean_ci_lower = round(mean - margin, 3)
        mean_ci_upper = round(mean + margin, 3)

    return {
        "n_observations": int(len(df)),
        "start_date": str(df["date"].min().date()),
        "end_date": str(df["date"].max().date()),
        "inferred_frequency": pd.infer_freq(df["date"]) or "irregular",
        "n_missing_values": int(values.isna().sum()),
        "mean": round(mean, 3),
        "mean_ci_lower": mean_ci_lower,
        "mean_ci_upper": mean_ci_upper,
        "confidence_level": confidence_level,
        "std": round(std, 3),
        "min": round(float(values.min()), 3),
        "max": round(float(values.max()), 3),
    }


def _mean_reversion_effect_size(values: np.ndarray, confidence_level: float = 0.95) -> dict:
    """Effect size for the ADF test: how strongly, not just whether, the
    series mean-reverts -- plus a confidence interval, since a bare point
    estimate of lambda/half-life overstates how precisely either is known.

    The ADF test itself only answers "is there a unit root," which says
    nothing about magnitude -- a series can be statistically significantly
    stationary while reverting so slowly it's practically useless for
    short-horizon forecasting, or so quickly the trend/seasonal signal
    barely matters next to it. This fits the classic Ornstein-Uhlenbeck-style
    regression underlying the ADF statistic itself, delta_y_t = lambda *
    y_{t-1} + mu + epsilon_t, via OLS (independent of ADF's own autolag
    selection, so it stays interpretable on its own), and reports:

    - lambda: the mean-reversion speed, with its OLS confidence interval.
      Negative means reverting (more negative = faster); zero or positive
      means no mean reversion at all.
    - half_life_periods: periods for half of a deviation from the series'
      long-run mean to decay, i.e. -ln(2)/lambda. None when lambda >= 0,
      since there's no finite half-life to report.
    - half_life_ci_lower / half_life_ci_upper: half-life is an INCREASING
      function of lambda on lambda < 0 (a more negative lambda means
      faster reversion, i.e. a shorter half-life), so the half-life CI's
      bounds come from lambda's CI bounds in the same order, not swapped:
      half_life_ci_lower from lambda_ci_lower, half_life_ci_upper from
      lambda_ci_upper. half_life_ci_upper is None (unbounded) whenever
      lambda's CI reaches non-negative territory -- the data can't rule
      out arbitrarily slow reversion at that end of the interval.
    """
    y = np.asarray(values, dtype=float)
    y_lag = y[:-1]
    delta_y = np.diff(y)
    design = add_constant(y_lag)
    fit = OLS(delta_y, design).fit()
    lam = float(fit.params[1])
    lam_ci_lower, lam_ci_upper = (float(v) for v in fit.conf_int(alpha=1 - confidence_level)[1])

    half_life = None
    half_life_ci_lower = None
    half_life_ci_upper = None
    if lam < 0:
        half_life = round(float(-np.log(2) / lam), 2)
        # lam_ci_lower <= lam < 0 is guaranteed (the CI contains the point
        # estimate), so this bound is always computable here.
        half_life_ci_lower = round(float(-np.log(2) / lam_ci_lower), 2)
        if lam_ci_upper < 0:
            half_life_ci_upper = round(float(-np.log(2) / lam_ci_upper), 2)
        # else: lambda's CI reaches >= 0, so half-life's upper bound is
        # unbounded -- leave half_life_ci_upper as None.

    return {
        "lambda": round(lam, 6),
        "lambda_ci_lower": round(lam_ci_lower, 6),
        "lambda_ci_upper": round(lam_ci_upper, 6),
        "half_life_periods": half_life,
        "half_life_ci_lower": half_life_ci_lower,
        "half_life_ci_upper": half_life_ci_upper,
    }


def _kpss_effect_size(series: pd.Series, regression: str = "c") -> dict:
    """Effect size for the KPSS test: how far the statistic sits from its
    5% critical value, expressed as a ratio.

    KPSS's own p-value is coarse -- statsmodels interpolates it from just
    four lookup-table points (10%, 5%, 2.5%, 1%) and clips it at the
    table's edges. That means a wildly non-stationary series and a barely
    non-stationary one can both report p_value=0.01, with the p-value
    alone giving no way to tell them apart. `effect_size` (kpss_statistic
    / critical_value_5pct) keeps distinguishing magnitude past that
    boundary: comfortably below 1 means well within the stationary
    region; values well above 1 mean the statistic exceeds the 5%
    critical value by that many multiples.

    The InterpolationWarning statsmodels raises when the p-value hits a
    table boundary is suppressed here on purpose: this effect size is
    specifically a more informative answer to the same limitation that
    warning is pointing at, not something being papered over.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=InterpolationWarning)
        kpss_stat, p_value, lags, crit = kpss(series, regression=regression, nlags="auto")

    crit_5pct = float(crit["5%"])
    return {
        "statistic": round(float(kpss_stat), 4),
        "p_value": round(float(p_value), 4),
        "lags": int(lags),
        "critical_value_5pct": crit_5pct,
        "effect_size": round(float(kpss_stat) / crit_5pct, 4),
    }


def _combined_stationarity_interpretation(adf_stationary: bool, kpss_stationary: bool) -> str:
    """Joint ADF/KPSS interpretation. The two tests have opposite null
    hypotheses (ADF: non-stationary; KPSS: stationary), so running both
    and reading them together is standard practice -- each test's blind
    spot is roughly the other's strength.
    """
    if adf_stationary and kpss_stationary:
        return "ADF and KPSS agree: series is likely stationary."
    if not adf_stationary and not kpss_stationary:
        return "ADF and KPSS agree: series is likely non-stationary; differencing may be needed."
    if adf_stationary and not kpss_stationary:
        return (
            "ADF and KPSS disagree: ADF rejects a unit root (stationary) but KPSS "
            "rejects stationarity. This combination commonly indicates the series is "
            "trend-stationary rather than level-stationary -- consider re-running with "
            "kpss_regression='ct', or detrending before further analysis."
        )
    return (
        "ADF and KPSS disagree: ADF fails to reject a unit root (non-stationary) but "
        "KPSS fails to reject stationarity. This combination is often inconclusive -- "
        "both tests can have limited power on short or borderline series; treat "
        "stationarity as genuinely uncertain rather than picking one test's verdict "
        "over the other."
    )


def check_stationarity(df: pd.DataFrame, kpss_regression: str = "c", confidence_level: float = 0.95) -> dict:
    """Augmented Dickey-Fuller AND KPSS tests for stationarity, each with
    an effect size, combined into one joint verdict.

    ADF's null hypothesis is that the series has a unit root
    (non-stationary); a small p-value (< 0.05) rejects that, suggesting
    stationarity. KPSS's null hypothesis is the OPPOSITE -- that the
    series IS stationary; a small p-value there rejects stationarity.
    Running both and reading them together is standard practice, because
    each test's blind spot is roughly the other's strength. See
    _combined_stationarity_interpretation for the four-way readout.

    Both tests alone only answer "stationary or not" -- neither says how
    strongly. This also reports:
    - a mean-reversion effect size AND confidence interval for ADF
      (`mean_reversion_lambda`, `mean_reversion_half_life_periods`, and
      their `_ci_lower`/`_ci_upper` bounds -- see
      _mean_reversion_effect_size). The half-life point estimate alone
      overstates precision; the CI shows how wide a range is actually
      consistent with the data.
    - an effect size for KPSS (`kpss_effect_size` -- see
      _kpss_effect_size), which stays informative even when KPSS's own
      p-value is clipped at a lookup-table boundary.

    Args:
        kpss_regression: "c" (default, stationary around a constant --
            the same implicit null ADF is tested against here) or "ct"
            (stationary around a deterministic trend).
        confidence_level: Confidence level for the mean-reversion
            lambda/half-life interval, e.g. 0.95 for 95%.
    """
    series = df["value"].dropna()

    adf_result = adfuller(series, autolag="AIC")
    adf_stat, adf_p_value = adf_result[0], adf_result[1]
    adf_stationary = bool(adf_p_value < 0.05)
    reversion = _mean_reversion_effect_size(series.to_numpy(dtype=float), confidence_level=confidence_level)

    kpss_result = _kpss_effect_size(series, regression=kpss_regression)
    kpss_stationary = bool(kpss_result["p_value"] >= 0.05)

    if reversion["half_life_periods"] is not None:
        upper_note = (
            f"{reversion['half_life_ci_upper']}"
            if reversion["half_life_ci_upper"] is not None
            else "unbounded (CI for lambda includes non-reverting values)"
        )
        reversion_note = (
            f"Mean-reversion half-life is ~{reversion['half_life_periods']} periods "
            f"({int(confidence_level * 100)}% CI: {reversion['half_life_ci_lower']} to {upper_note}) "
            "-- small values correct quickly, large ones are slow even if statistically detectable."
        )
    else:
        reversion_note = "No finite mean-reversion half-life (lambda >= 0 in the ADF regression)."
    kpss_effect_note = (
        f"KPSS statistic is {kpss_result['effect_size']}x its 5% critical value"
        + (" (comfortably below it)." if kpss_result["effect_size"] < 1 else " (exceeds it).")
    )

    return {
        "adf_statistic": round(float(adf_stat), 4),
        "adf_p_value": round(float(adf_p_value), 4),
        "adf_is_likely_stationary": adf_stationary,
        "mean_reversion_lambda": reversion["lambda"],
        "mean_reversion_lambda_ci_lower": reversion["lambda_ci_lower"],
        "mean_reversion_lambda_ci_upper": reversion["lambda_ci_upper"],
        "mean_reversion_half_life_periods": reversion["half_life_periods"],
        "mean_reversion_half_life_ci_lower": reversion["half_life_ci_lower"],
        "mean_reversion_half_life_ci_upper": reversion["half_life_ci_upper"],
        "kpss_statistic": kpss_result["statistic"],
        "kpss_p_value": kpss_result["p_value"],
        "kpss_lags": kpss_result["lags"],
        "kpss_critical_value_5pct": kpss_result["critical_value_5pct"],
        "kpss_effect_size": kpss_result["effect_size"],
        "kpss_regression": kpss_regression,
        "kpss_is_likely_stationary": kpss_stationary,
        "confidence_level": confidence_level,
        "interpretation": (
            _combined_stationarity_interpretation(adf_stationary, kpss_stationary)
            + " "
            + reversion_note
            + " "
            + kpss_effect_note
        ),
    }


def seasonal_decomposition_summary(df: pd.DataFrame, period: int = 7) -> dict:
    """Classical seasonal decomposition (additive). Returns the relative
    strength of trend and seasonal components vs. the residual, which is a
    quick proxy for how much seasonality/trend structure exists.

    period=7 assumes daily data with weekly seasonality; pass period=12 for
    monthly data with yearly seasonality, etc.
    """
    series = df.set_index("date")["value"]
    if len(series) < period * 2:
        return {"error": f"Series too short to decompose with period={period}."}

    decomposition = seasonal_decompose(series, model="additive", period=period, extrapolate_trend="freq")

    resid_var = float(np.nanvar(decomposition.resid))
    seasonal_var = float(np.nanvar(decomposition.seasonal))
    trend_var = float(np.nanvar(decomposition.trend))
    total_var = float(np.nanvar(series))

    def strength(component_var: float) -> float:
        # Strength-of-signal heuristic (Hyndman & Athanasopoulos):
        # bounded roughly in [0, 1], higher = stronger component relative to noise.
        denom = component_var + resid_var
        return round(max(0.0, 1 - resid_var / denom), 4) if denom > 0 else 0.0

    return {
        "period_assumed": period,
        "trend_strength": strength(trend_var),
        "seasonal_strength": strength(seasonal_var),
        "residual_variance_share": round(resid_var / total_var, 4) if total_var > 0 else None,
        "interpretation": (
            f"Trend strength {strength(trend_var):.2f} and seasonal strength "
            f"{strength(seasonal_var):.2f} on a 0-1 scale; higher means that "
            "component explains more of the variation relative to noise."
        ),
    }


def detect_seasonality_period(df: pd.DataFrame, min_period: int = 2, max_period: Optional[int] = None) -> dict:
    """Find the dominant cyclical period in a series via its periodogram,
    with a significance test -- so the CALLER doesn't have to already
    know/guess a period before using seasonal_decomposition_summary or
    reading acf_pacf_summary's significant lags for a periodic pattern.

    Ranks candidate periods (within [min_period, max_period], default
    max_period = n // 2) by relative spectral power -- each period's share
    of total periodogram power, which doubles as an effect size: a period
    responsible for 60% of total power is a very different finding from
    one responsible for 4%, even if both are the top-ranked candidate.

    Significance of the single strongest frequency in the FULL periodogram
    (not just the [min_period, max_period] range -- the significance test
    needs the true, complete set of Fourier frequencies to be valid) is
    assessed with Fisher's g-test for hidden periodicity (Fisher, 1929):
    g = (power at the strongest frequency) / (total power across all
    frequencies). This implementation uses the standard conservative
    upper-bound approximation on the p-value, P(g > g0) <= q*(1-g0)^(q-1)
    (q = number of non-zero Fourier frequencies) -- the leading term of
    the full alternating-series formula, and the same approximation used
    by, e.g., the GeneCycle R package's fisher.g.test.

    The globally strongest frequency can correspond to a period OUTSIDE
    [min_period, max_period] (e.g. period ~1-2, likely noise/edge effects,
    or a period near the series length, likely trend) -- check
    dominant_period_in_reported_range before treating the significance
    test as endorsing one of the reported candidate periods specifically.
    """
    series = df["value"].dropna().to_numpy(dtype=float)
    n = len(series)
    if n < 8:
        return {"error": f"Series too short ({n} observations) for periodogram-based seasonality detection."}
    if max_period is None:
        max_period = n // 2

    demeaned = series - series.mean()
    freqs, power = periodogram(demeaned)
    freqs = freqs[1:]  # drop the zero-frequency term (undefined period)
    power = power[1:]
    q = len(freqs)  # number of non-zero Fourier frequencies, for the g-test

    total_power = float(power.sum())
    if q == 0 or total_power <= 0:
        return {"error": "Series has no variance to analyze (constant series)."}

    max_idx = int(np.argmax(power))
    g0 = float(power[max_idx] / total_power)
    dominant_period = float(1.0 / freqs[max_idx])
    p_value = float(min(1.0, q * (1.0 - g0) ** (q - 1)))
    is_significant = bool(p_value < 0.05)

    periods = 1.0 / freqs
    in_range = (periods >= min_period) & (periods <= max_period)
    candidate_periods = periods[in_range]
    candidate_power = power[in_range]

    top_candidate_periods = []
    if len(candidate_power) > 0:
        order = np.argsort(candidate_power)[::-1]
        top_candidate_periods = [
            {
                "period": round(float(candidate_periods[i]), 2),
                "relative_power": round(float(candidate_power[i]) / total_power, 4),
            }
            for i in order[:5]
        ]

    dominant_in_range = bool(min_period <= dominant_period <= max_period)

    if is_significant and dominant_in_range:
        interpretation = (
            f"Fisher's g-test rejects the no-periodicity null (p={round(p_value, 4)}): the "
            f"dominant cycle has period ~{round(dominant_period, 2)}, accounting for "
            f"{round(g0 * 100, 1)}% of total periodogram power."
        )
    elif is_significant:
        interpretation = (
            f"Fisher's g-test rejects the no-periodicity null (p={round(p_value, 4)}), but the "
            f"single strongest frequency corresponds to period ~{round(dominant_period, 2)}, "
            f"outside the [{min_period}, {max_period}] range treated as plausible seasonality "
            "(likely a trend or edge-effect artifact, not true seasonality). See "
            "top_candidate_periods for the strongest candidate actually within that range."
        )
    else:
        interpretation = (
            f"Fisher's g-test fails to reject the no-periodicity null (p={round(p_value, 4)}): "
            "no single frequency dominates the periodogram enough to call this a statistically "
            "significant cycle. top_candidate_periods still lists the largest relative-power "
            "candidates for reference, but treat them as suggestive, not confirmed."
        )

    return {
        "n_observations": n,
        "dominant_period": round(dominant_period, 2),
        "dominant_period_relative_power": round(g0, 4),
        "dominant_period_in_reported_range": dominant_in_range,
        "fisher_g_statistic": round(g0, 4),
        "fisher_g_p_value": round(p_value, 4),
        "is_significant_periodicity": is_significant,
        "top_candidate_periods": top_candidate_periods,
        "interpretation": interpretation,
    }


def _acf_pacf_raw(df: pd.DataFrame, n_lags: int, alpha: float) -> tuple:
    """Shared raw computation behind acf_pacf_summary AND plot_tools.py's
    plot_acf_pacf -- factored out so the plot's significance shading and
    the JSON tool's significant_acf_lags can never silently disagree.
    Returns (acf_vals, acf_confint, pacf_vals, n_lags_used).
    """
    series = df["value"].dropna()
    n_lags = min(n_lags, len(series) // 2 - 1)
    acf_vals, acf_confint = acf(series, nlags=n_lags, fft=True, alpha=alpha)
    pacf_vals = pacf(series, nlags=n_lags)
    return acf_vals, acf_confint, pacf_vals, n_lags


def acf_pacf_summary(df: pd.DataFrame, n_lags: int = 21, alpha: float = 0.05) -> dict:
    """Autocorrelation / partial autocorrelation at selected lags. Useful for
    spotting seasonality period and deciding AR/MA order.

    Flags lags whose confidence interval excludes zero, using statsmodels'
    Bartlett-formula per-lag confidence intervals -- NOT a single global
    threshold. The correct standard error for ACF at lag k grows with the
    cumulative squared autocorrelation of lags 1..k-1 (as if the series
    were an MA(k-1)); a uniform 1.96/sqrt(n) threshold, as an earlier
    version of this tool used, is only actually correct at lag 1 and
    understates the threshold at later lags. Each flagged lag reports an
    effect size -- the ACF magnitude as a multiple of its own (per-lag)
    interval half-width -- so a lag that barely clears its threshold and
    one that clears it by 5x aren't both just "significant."

    Args:
        alpha: Significance level for the per-lag confidence intervals,
            e.g. 0.05 for 95% intervals.
    """
    acf_vals, acf_confint, pacf_vals, n_lags = _acf_pacf_raw(df, n_lags, alpha)

    significant_acf_lags = []
    for i in range(1, len(acf_vals)):
        ci_lower, ci_upper = acf_confint[i]
        half_width = float(ci_upper - ci_lower) / 2.0
        if half_width > 0 and abs(acf_vals[i]) > half_width:
            significant_acf_lags.append(
                {
                    "lag": i,
                    "acf": round(float(acf_vals[i]), 4),
                    "ci_lower": round(float(ci_lower), 4),
                    "ci_upper": round(float(ci_upper), 4),
                    "effect_size": round(abs(float(acf_vals[i])) / half_width, 4),
                }
            )
    # Strongest first, so capping for brevity below keeps the most
    # significant lags rather than just the earliest ones chronologically.
    significant_acf_lags.sort(key=lambda entry: entry["effect_size"], reverse=True)

    return {
        "n_lags_checked": n_lags,
        "significance_alpha": alpha,
        "significant_acf_lags": significant_acf_lags[:10],  # cap for brevity, strongest first
        "acf_at_lag_1": round(float(acf_vals[1]), 4) if len(acf_vals) > 1 else None,
        "acf_at_lag_7": round(float(acf_vals[7]), 4) if len(acf_vals) > 7 else None,
        "pacf_at_lag_1": round(float(pacf_vals[1]), 4) if len(pacf_vals) > 1 else None,
    }


def detect_anomalies_zscore(df: pd.DataFrame, z_threshold: float = 3.0) -> dict:
    """Flag points whose value is more than z_threshold standard deviations
    from a rolling mean, i.e. simple anomaly/outlier detection.

    Reports each flagged point's actual z-score as an effect size -- not
    just that it crossed z_threshold, but by how much. A z-score of 3.1 and
    a z-score of 11 both clear a threshold of 3.0, but they're very
    different findings; the threshold alone can't tell them apart.
    """
    series = df["value"]
    rolling_mean = series.rolling(window=14, min_periods=1, center=True).mean()
    rolling_std = series.rolling(window=14, min_periods=1, center=True).std().replace(0, np.nan)

    z_scores = (series - rolling_mean) / rolling_std
    flagged_mask = z_scores.abs() > z_threshold
    flagged = df.loc[flagged_mask, ["date", "value"]].copy()
    flagged["z_score"] = z_scores.loc[flagged_mask]

    # Most extreme first, so capping for brevity below keeps the biggest
    # anomalies rather than just the earliest ones chronologically.
    flagged = flagged.reindex(flagged["z_score"].abs().sort_values(ascending=False).index)

    anomalies = [
        {
            "date": str(row["date"].date()),
            "value": round(float(row["value"]), 3),
            "z_score": round(float(row["z_score"]), 3),
        }
        for _, row in flagged.iterrows()
    ]

    return {
        "z_threshold": z_threshold,
        "n_anomalies_flagged": int(len(flagged)),
        "max_abs_z_score": round(float(flagged["z_score"].abs().max()), 3) if len(flagged) else None,
        "anomalies": anomalies[:15],  # cap for brevity, most extreme first
    }


def _rolling_mad(series: pd.Series, rolling_median: pd.Series, window: int) -> pd.Series:
    """Rolling median absolute deviation, using each window's OWN median
    as the reference point (not a mismatched running comparison) -- the
    `.apply` here recomputes np.median(x) on each window slice `x`
    internally, which is guaranteed to equal the corresponding entry of
    `rolling_median` as long as both share identical window/min_periods/
    center settings (checked by the caller).
    """
    def mad(x: np.ndarray) -> float:
        return np.median(np.abs(x - np.median(x)))

    return series.rolling(window=window, min_periods=1, center=True).apply(mad, raw=True)


def detect_anomalies_robust_zscore(df: pd.DataFrame, z_threshold: float = 3.5, window: int = 14) -> dict:
    """Robust anomaly detection using a rolling MODIFIED z-score (rolling
    median + MAD, Iglewicz & Hoya 1993) instead of detect_anomalies_zscore's
    rolling mean + std.

    detect_anomalies_zscore's rolling mean/std is distorted by the very
    anomaly it's trying to measure: a single large spike inside its
    14-point rolling window inflates that window's own std, diluting the
    z-score of the point that caused it -- confirmed empirically during
    development, where a +500 spike on a ~200-scale series only scored
    z=3.44, not something far higher. Median and MAD are far less
    sensitive to a single outlier within a window (the median of 14
    points barely moves if only one is wildly off), so this detector
    doesn't have that self-dilution problem.

    modified_z_i = 0.6745 * (x_i - rolling_median_i) / rolling_MAD_i

    0.6745 rescales MAD to be comparable to a standard deviation under
    normality, so z_threshold here is on roughly the same scale as
    detect_anomalies_zscore's -- but the DEFAULT is 3.5, not 3.0, per
    Iglewicz & Hoya's recommendation for the modified z-score
    specifically (not simply copied from the non-robust version).

    Prefer this over detect_anomalies_zscore when you suspect a single
    large anomaly might be masking itself (or nearby points) via
    self-dilution; prefer detect_anomalies_zscore when you want the
    conventional mean/std definition specifically (e.g. to match a
    downstream process that assumes it).
    """
    series = df["value"]
    rolling_median = series.rolling(window=window, min_periods=1, center=True).median()
    rolling_mad = _rolling_mad(series, rolling_median, window).replace(0, np.nan)

    modified_z = 0.6745 * (series - rolling_median) / rolling_mad
    flagged_mask = modified_z.abs() > z_threshold
    flagged = df.loc[flagged_mask, ["date", "value"]].copy()
    flagged["modified_z_score"] = modified_z.loc[flagged_mask]

    # Most extreme first, so capping for brevity below keeps the biggest
    # anomalies rather than just the earliest ones chronologically.
    flagged = flagged.reindex(flagged["modified_z_score"].abs().sort_values(ascending=False).index)

    anomalies = [
        {
            "date": str(row["date"].date()),
            "value": round(float(row["value"]), 3),
            "modified_z_score": round(float(row["modified_z_score"]), 3),
        }
        for _, row in flagged.iterrows()
    ]

    return {
        "z_threshold": z_threshold,
        "window": window,
        "n_anomalies_flagged": int(len(flagged)),
        "max_abs_modified_z_score": (
            round(float(flagged["modified_z_score"].abs().max()), 3) if len(flagged) else None
        ),
        "anomalies": anomalies[:15],  # cap for brevity, most extreme first
    }


def _cusum_statistic(values: np.ndarray) -> tuple:
    """Standardized CUSUM mean-shift statistic, vectorized over every
    candidate split point k=1..n-1: compares the mean of values[:k] to
    the mean of values[k:], weighted by segment sizes and standardized by
    the whole segment's std. Returns (best_k, best_statistic), or
    (None, 0.0) if the segment is too short or has zero variance.

    This flags a shift in MEAN LEVEL specifically -- not a change in
    variance or trend slope alone, and not the same job as
    detect_anomalies_zscore/detect_anomalies_robust_zscore (a single
    large point spike vs. a lasting shift in the series' level).
    """
    n = len(values)
    if n < 4:
        return None, 0.0
    overall_std = float(np.std(values, ddof=1))
    if overall_std == 0:
        return None, 0.0

    k = np.arange(1, n)
    cumsum = np.cumsum(values)
    total = cumsum[-1]
    mean_before = cumsum[:-1] / k
    mean_after = (total - cumsum[:-1]) / (n - k)
    stats = np.sqrt(k * (n - k) / n) * np.abs(mean_before - mean_after) / overall_std

    best_idx = int(np.argmax(stats))
    return int(k[best_idx]), float(stats[best_idx])


def _cusum_p_value(values: np.ndarray, observed_stat: float, n_permutations: int, rng: np.random.Generator) -> float:
    """Permutation-test p-value for the CUSUM statistic: shuffle the
    segment (destroying any real changepoint while preserving its
    values' distribution) n_permutations times, and see how often a
    shuffled segment's best CUSUM statistic meets or exceeds the observed
    one. A closed-form asymptotic distribution exists for this statistic,
    but its critical values require care to get right; a permutation
    test sidesteps that and is exact/nonparametric by construction --
    the same reasoning ts-deploy's forecast_ets already uses simulation
    (n_simulations) for its prediction intervals rather than a
    closed-form formula.
    """
    shuffled = values.copy()
    count_exceeding = 0
    for _ in range(n_permutations):
        rng.shuffle(shuffled)
        _, stat = _cusum_statistic(shuffled)
        if stat >= observed_stat:
            count_exceeding += 1
    # +1 smoothing in both numerator and denominator: standard permutation-
    # test convention, avoids ever reporting p=0 from a finite sample.
    return (count_exceeding + 1) / (n_permutations + 1)


def _binary_segmentation(
    values: np.ndarray,
    start: int,
    end: int,
    alpha: float,
    min_segment_size: int,
    n_permutations: int,
    rng: np.random.Generator,
    max_changepoints: int,
    changepoints: list,
) -> None:
    """Recursively find the single most likely changepoint in
    values[start:end]; if significant, record it and recurse into both
    halves. Standard binary segmentation (Scott & Knott 1974; Vostrikova
    1981) -- a well-established heuristic for MULTIPLE changepoints, built
    from repeated single-changepoint (CUSUM) tests.
    """
    if len(changepoints) >= max_changepoints:
        return
    if end - start < 2 * min_segment_size:
        return

    segment = values[start:end]
    k, stat = _cusum_statistic(segment)
    if k is None or k < min_segment_size or (len(segment) - k) < min_segment_size:
        return

    p_value = _cusum_p_value(segment, stat, n_permutations, rng)
    if p_value >= alpha:
        return

    split = start + k
    changepoints.append({"index": split, "statistic": stat, "p_value": p_value})
    _binary_segmentation(values, start, split, alpha, min_segment_size, n_permutations, rng, max_changepoints, changepoints)
    _binary_segmentation(values, split, end, alpha, min_segment_size, n_permutations, rng, max_changepoints, changepoints)


def detect_changepoints(
    df: pd.DataFrame,
    alpha: float = 0.05,
    min_segment_size: int = 10,
    max_changepoints: int = 5,
    n_permutations: int = 500,
    seed: int = 42,
) -> dict:
    """Detect structural breaks (lasting shifts in the series' MEAN
    LEVEL) using binary segmentation with a standardized CUSUM statistic
    and a permutation test for significance -- a different job from
    detect_anomalies_zscore/detect_anomalies_robust_zscore, which flag
    individual POINT outliers, not a persistent shift from one regime to
    the next. A single very large, isolated spike can trip an anomaly
    detector without being a real changepoint; a modest but sustained
    level shift can be a real changepoint without tripping either
    anomaly detector.

    Each detected changepoint reports Cohen's d (pooled-std standardized
    mean difference between the segments immediately before and after)
    as an effect size, plus the CUSUM statistic and permutation p-value
    from the split that found it.

    KNOWN LIMITATION (by design, not a bug): binary segmentation's
    per-split p-values are LOCAL tests within whatever segment existed at
    the time of that split -- the algorithm does not give an exact global
    significance guarantee for the full SET of changepoints it reports,
    the way a single hypothesis test would. This is a standard, accepted
    tradeoff for this class of algorithm, not unique to this
    implementation; treat max_changepoints and alpha as tuning knobs, not
    as controlling an exact family-wise error rate.

    The permutation test is seeded (default 42) for reproducibility --
    the same series and settings always return the same changepoints.

    Args:
        alpha: Significance level for each split's permutation test.
        min_segment_size: Minimum observations required on each side of
            a candidate split; also the minimum resulting segment size.
        max_changepoints: Upper bound on how many changepoints to report.
        n_permutations: Permutations used per significance test. Higher
            is more precise but slower (roughly linear in this value).
        seed: Random seed for the permutation test's shuffling, for
            reproducibility.
    """
    series = df["value"].dropna().reset_index(drop=True)
    values = series.to_numpy(dtype=float)
    n = len(values)
    if n < 2 * min_segment_size:
        return {
            "error": (
                f"Series too short ({n} observations) for changepoint detection with "
                f"min_segment_size={min_segment_size} (need at least {2 * min_segment_size})."
            )
        }

    dates = df["date"].reset_index(drop=True)
    rng = np.random.default_rng(seed)
    raw_changepoints: list = []
    _binary_segmentation(values, 0, n, alpha, min_segment_size, n_permutations, rng, max_changepoints, raw_changepoints)
    raw_changepoints.sort(key=lambda c: c["index"])

    boundaries = [0] + [cp["index"] for cp in raw_changepoints] + [n]
    results = []
    for i, cp in enumerate(raw_changepoints):
        seg_before = values[boundaries[i]:boundaries[i + 1]]
        seg_after = values[boundaries[i + 1]:boundaries[i + 2]]
        n1, n2 = len(seg_before), len(seg_after)
        mean_before, mean_after = float(np.mean(seg_before)), float(np.mean(seg_after))
        s1, s2 = np.std(seg_before, ddof=1), np.std(seg_after, ddof=1)
        pooled_var_df = n1 + n2 - 2
        pooled_std = float(np.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / pooled_var_df)) if pooled_var_df > 0 else 0.0
        cohens_d = round(abs(mean_after - mean_before) / pooled_std, 4) if pooled_std > 0 else None

        results.append(
            {
                "date": str(dates.iloc[cp["index"]].date()),
                "index": cp["index"],
                "mean_before": round(mean_before, 3),
                "mean_after": round(mean_after, 3),
                "cohens_d_effect_size": cohens_d,
                "cusum_statistic": round(cp["statistic"], 4),
                "p_value": round(cp["p_value"], 4),
            }
        )

    if not results:
        interpretation = f"No statistically significant structural breaks found (alpha={alpha}) in {n} observations."
    else:
        interpretation = f"{len(results)} structural break(s) found: " + "; ".join(
            f"{r['date']} (mean {r['mean_before']} -> {r['mean_after']}, "
            f"Cohen's d={r['cohens_d_effect_size']}, p={r['p_value']})"
            for r in results
        )

    return {
        "n_observations": n,
        "alpha": alpha,
        "n_changepoints_found": len(results),
        "changepoints": results,
        "interpretation": interpretation,
    }


# Registry used by agent.py to expose these as callable tools by name.
TOOL_REGISTRY: dict[str, Callable[..., dict]] = {
    "basic_stats": basic_stats,
    "check_stationarity": check_stationarity,
    "seasonal_decomposition_summary": seasonal_decomposition_summary,
    "detect_seasonality_period": detect_seasonality_period,
    "acf_pacf_summary": acf_pacf_summary,
    "detect_anomalies_zscore": detect_anomalies_zscore,
    "detect_anomalies_robust_zscore": detect_anomalies_robust_zscore,
    "detect_changepoints": detect_changepoints,
}


if __name__ == "__main__":
    from omen.data_prep import generate_synthetic_series

    df = generate_synthetic_series()
    for name, fn in TOOL_REGISTRY.items():
        print(f"\n--- {name} ---")
        print(json.dumps(fn(df), indent=2))
