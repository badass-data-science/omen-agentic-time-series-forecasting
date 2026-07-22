"""
monitor_tools.py

Layer 4: closes the loop after deployment. Once time has passed and real
observations exist for at least part of a forecast's horizon, this checks
whether the forecast is still tracking reality, whether the underlying
series has drifted from what earlier layers were trained on, and combines
both signals into a retrain recommendation.

Design note: compare_forecast_to_actuals and detect_data_drift are
diagnostic (return numbers for the agent to reason about), but
recommend_retraining is deliberately a DETERMINISTIC decision function with
explicit, adjustable thresholds -- not a judgment call left to the model.
This mirrors the earlier point about static workflows vs. agentic
judgment: "should we retrain" is exactly the kind of decision worth being
reproducible given the same inputs, not re-derived by an LLM each time.
"""

from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, norm as _norm, ttest_ind


def compute_metrics(y_true: Any, y_pred: Any) -> dict:
    """MAE, RMSE, and MAPE (%) -- same definition Layer 2 used, so numbers
    here are directly comparable to a Layer 2 backtest result."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    errors = y_true - y_pred

    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))

    nonzero_mask = np.abs(y_true) > 1e-8
    if nonzero_mask.any():
        mape = float(np.mean(np.abs(errors[nonzero_mask] / y_true[nonzero_mask])) * 100)
    else:
        mape = None

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape_pct": round(mape, 4) if mape is not None else None,
    }


def _bootstrap_metric_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> dict:
    """Bootstrap confidence intervals for MAE, RMSE, and MAPE: resample
    PAIRED (actual, forecast) points with replacement n_bootstrap times,
    recompute each metric per resample, take percentiles. Deliberately the
    same technique (and the same field names: mae_ci_lower/upper, etc.)
    as ts-forecaster's model_tools.py::_bootstrap_metric_ci, duplicated
    here rather than imported cross-layer (same precedent as
    deploy/forecast_tools.py's _aicc/_build_lag_features) -- a monitoring
    comparison drawn from a handful of just-elapsed forecast dates has the
    same "modest sample, single window" uncertainty a Layer 2 backtest
    does, arguably more consequential since it's about real post-
    deployment performance, not a backtest.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    n = len(y_true)

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_bootstrap, n))
    resampled_true = y_true[idx]
    resampled_pred = y_pred[idx]
    errors = resampled_true - resampled_pred

    mae_samples = np.mean(np.abs(errors), axis=1)
    rmse_samples = np.sqrt(np.mean(errors**2, axis=1))

    nonzero_mask = np.abs(resampled_true) > 1e-8
    with np.errstate(invalid="ignore", divide="ignore"):
        pct_errors = np.where(nonzero_mask, np.abs(errors / resampled_true), np.nan)
    mape_samples = np.nanmean(pct_errors, axis=1) * 100

    alpha = 1 - confidence_level

    def _percentile_ci(samples: np.ndarray) -> tuple:
        samples = samples[~np.isnan(samples)]
        if len(samples) == 0:
            return None, None
        lower = round(float(np.percentile(samples, 100 * alpha / 2)), 4)
        upper = round(float(np.percentile(samples, 100 * (1 - alpha / 2))), 4)
        return lower, upper

    mae_ci = _percentile_ci(mae_samples)
    rmse_ci = _percentile_ci(rmse_samples)
    mape_ci = _percentile_ci(mape_samples)

    return {
        "mae_ci_lower": mae_ci[0],
        "mae_ci_upper": mae_ci[1],
        "rmse_ci_lower": rmse_ci[0],
        "rmse_ci_upper": rmse_ci[1],
        "mape_pct_ci_lower": mape_ci[0],
        "mape_pct_ci_upper": mape_ci[1],
    }


def compute_metrics_with_ci(
    y_true: Any,
    y_pred: Any,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
) -> dict:
    """compute_metrics's point estimates (MAE, RMSE, MAPE), plus a
    bootstrap confidence interval for each -- see _bootstrap_metric_ci.
    Additive over compute_metrics, not a rename: every pre-existing field
    name is unchanged, only the CI fields are new.
    """
    metrics = compute_metrics(y_true, y_pred)
    ci = _bootstrap_metric_ci(y_true, y_pred, n_bootstrap=n_bootstrap, confidence_level=confidence_level, seed=seed)
    return {**metrics, **ci, "ci_confidence_level": confidence_level, "ci_n_bootstrap": n_bootstrap}


def _wilson_score_interval(successes: int, n: int, confidence_level: float = 0.95) -> tuple:
    """Wilson score confidence interval for a binomial proportion --
    better-behaved than the normal approximation for small n or a
    proportion near 0/1, both common here since interval coverage is
    often computed from a handful of just-elapsed forecast dates. Returns
    (lower_pct, upper_pct), or (None, None) if n == 0.
    """
    if n == 0:
        return None, None
    z = float(_norm.ppf(1 - (1 - confidence_level) / 2))
    p_hat = successes / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    half_width = (z / denom) * np.sqrt((p_hat * (1 - p_hat) / n) + (z**2 / (4 * n**2)))
    lower = max(0.0, center - half_width)
    upper = min(1.0, center + half_width)
    return round(lower * 100, 2), round(upper * 100, 2)


def _residual_outliers(matched: list, z_threshold: float = 3.5) -> dict:
    """Flags matched-point residuals (actual - forecast) that look like
    outliers relative to the rest of the elapsed-horizon comparison, using
    a modified z-score (median + MAD, Iglewicz & Hoya 1993) -- the same
    technique and default threshold as ts-analyst's
    detect_anomalies_robust_zscore, applied here to a single fixed set of
    residuals rather than a rolling window (the elapsed horizon is
    typically too short for a rolling window to make sense).

    The point: an aggregate MAPE over the elapsed horizon can't tell "the
    forecast missed by a little every day" from "the forecast was fine
    except for one wild day (a promotion, an outage)" -- these call for
    different responses, and only one of them is evidence the MODEL itself
    needs retraining. metrics_excluding_outliers lets the caller see how
    much a small number of unusual days are inflating the aggregate error.

    KNOWN LIMITATION, not a bug: if half or more of the residuals are
    EXACTLY identical (most realistically, exactly 0 -- a suspiciously
    perfect forecast on most days), the median absolute deviation itself
    degenerates to 0, and every point's modified z-score collapses to 0
    regardless of how extreme any other single residual is -- the same
    self-dilution failure mode ts-analyst's original detect_anomalies_zscore
    had before the robust version was built, just triggered by a different
    (rarer, but not impossible) condition. Guarded by falling back to
    all-zero z-scores (flags nothing) rather than raising or dividing by
    zero, but a genuine outlier CAN be masked in this specific edge case.
    """
    residuals = np.array([m["actual"] - m["forecast"] for m in matched], dtype=float)
    median_resid = float(np.median(residuals))
    mad = float(np.median(np.abs(residuals - median_resid)))

    if mad > 0:
        modified_z = 0.6745 * (residuals - median_resid) / mad
    else:
        modified_z = np.zeros_like(residuals)

    is_outlier = np.abs(modified_z) > z_threshold
    flagged_dates = [m["date"] for m, flagged in zip(matched, is_outlier) if flagged]

    metrics_excluding_outliers = None
    n_kept = int((~is_outlier).sum())
    if 0 < n_kept < len(matched) and n_kept >= 2:
        y_true_clean = [m["actual"] for m, flagged in zip(matched, is_outlier) if not flagged]
        y_pred_clean = [m["forecast"] for m, flagged in zip(matched, is_outlier) if not flagged]
        metrics_excluding_outliers = compute_metrics(y_true_clean, y_pred_clean)

    return {
        "z_threshold": z_threshold,
        "flagged_dates": flagged_dates,
        "max_abs_modified_z_score": round(float(np.max(np.abs(modified_z))), 4) if len(modified_z) else None,
        "metrics_excluding_outliers": metrics_excluding_outliers,
        "per_point": [
            {"date": m["date"], "residual": round(float(r), 4), "modified_z_score": round(float(z), 4)}
            for m, r, z in zip(matched, residuals, modified_z)
        ],
        "interpretation": (
            f"{len(flagged_dates)} of {len(matched)} matched date(s) flagged as residual outliers "
            f"(modified z-score > {z_threshold}). "
            + (
                (
                    f"Excluding them, MAPE would be {metrics_excluding_outliers['mape_pct']}% instead of "
                    "the full-set figure above -- consider whether the aggregate error is being driven by "
                    "a small number of unusual days rather than a systematic miss before treating it as "
                    "evidence the model itself needs retraining."
                )
                if metrics_excluding_outliers is not None
                else "Not enough non-outlier points remain for a clean comparison."
            )
            if flagged_dates
            else "No residual outliers flagged -- the aggregate error above isn't being driven by a small number of unusual days."
        ),
    }


def compare_forecast_to_actuals(
    forecast: list,
    df: pd.DataFrame,
    confidence_level: float = 0.95,
    n_bootstrap: int = 1000,
    seed: int = 42,
    outlier_z_threshold: float = 3.5,
) -> dict:
    """Match a previously produced forecast (the list of {date, forecast,
    lower?, upper?} dicts a ts-deploy tool returned) against real observed
    values now present in the updated series, and report:
    - error metrics over whatever portion of the horizon has actually
      elapsed, WITH a bootstrap confidence interval on each (see
      compute_metrics_with_ci) -- a comparison drawn from just a few
      elapsed forecast dates has real sampling uncertainty of its own,
      same reasoning as ts-forecaster's backtest metric CIs.
    - prediction interval coverage, if the forecast included one: what
      fraction of realized actuals actually fell inside their interval,
      vs. the nominal confidence level, WITH a Wilson score confidence
      interval on the coverage percentage itself (see
      _wilson_score_interval) -- coverage is a proportion computed from
      whatever's elapsed so far, often a small handful of dates, so the
      point estimate alone can overstate how precisely "is this
      calibrated" is actually known. This is supplementary to, and does
      NOT change, `well_calibrated`'s existing threshold-based verdict
      (kept deliberately identical to ts-forecaster's mirrored
      backtest_interval_coverage check, see AGENTS.md).
    - residual outliers (see _residual_outliers): whether the aggregate
      error is being driven by a small number of unusual days rather than
      a systematic miss.
    """
    actuals_by_date = {str(row["date"].date()): row["value"] for _, row in df.iterrows()}

    matched = []
    for point in forecast:
        date_str = point.get("date")
        if date_str is None or "forecast" not in point:
            continue  # skip truncation-note placeholder entries
        if date_str in actuals_by_date:
            matched.append(
                {
                    "date": date_str,
                    "actual": actuals_by_date[date_str],
                    "forecast": point["forecast"],
                    "lower": point.get("lower"),
                    "upper": point.get("upper"),
                }
            )

    if not matched:
        return {
            "error": (
                "No actual observations yet exist for any forecasted date in this CSV. "
                "Re-run this once new data covering at least part of the forecast horizon "
                "has been collected."
            )
        }

    y_true = [m["actual"] for m in matched]
    y_pred = [m["forecast"] for m in matched]
    metrics = compute_metrics_with_ci(y_true, y_pred, n_bootstrap=n_bootstrap, confidence_level=confidence_level, seed=seed)

    coverage_result: dict = {"interval_available": False}
    has_intervals = all(m["lower"] is not None and m["upper"] is not None for m in matched)
    if has_intervals:
        within = sum(1 for m in matched if m["lower"] <= m["actual"] <= m["upper"])
        coverage_pct = round(100 * within / len(matched), 2)
        nominal_pct = round(confidence_level * 100, 2)
        ci_lower, ci_upper = _wilson_score_interval(within, len(matched), confidence_level)
        coverage_result = {
            "interval_available": True,
            "empirical_coverage_pct": coverage_pct,
            "empirical_coverage_ci_lower": ci_lower,
            "empirical_coverage_ci_upper": ci_upper,
            "nominal_confidence_pct": nominal_pct,
            "well_calibrated": bool(abs(coverage_pct - nominal_pct) <= 15),
            "interpretation": (
                f"{coverage_pct}% of realized actuals fell within their prediction interval "
                f"(Wilson score {int(confidence_level * 100)}% CI: [{ci_lower}%, {ci_upper}%], "
                f"n={len(matched)}), vs. a nominal {nominal_pct}%. "
                + (
                    "Reasonably close to nominal -- interval looks calibrated."
                    if abs(coverage_pct - nominal_pct) <= 15
                    else "Notably off from nominal -- the interval is likely too narrow (if "
                    "coverage is low) or too wide (if coverage is much higher than nominal), "
                    "and shouldn't be trusted at face value."
                )
                + (
                    " Note the wide CI above given the small number of matched dates so far -- "
                    "treat the calibration verdict as provisional until more observations accumulate."
                    if ci_lower is not None and (ci_upper - ci_lower) > 30
                    else ""
                )
            ),
        }

    return {
        "n_dates_compared": len(matched),
        "date_range_compared": [matched[0]["date"], matched[-1]["date"]],
        "backtest_style_metrics": metrics,
        "interval_coverage": coverage_result,
        "residual_outliers": _residual_outliers(matched, z_threshold=outlier_z_threshold),
        "matched_points": matched,
    }


def detect_data_drift(
    df: pd.DataFrame,
    recent_window_size: int = 30,
    reference_window_size: int = 90,
) -> dict:
    """Compare the most recent `recent_window_size` observations against a
    reference window of `reference_window_size` observations taken
    immediately before it, using two tests:
    - Welch's t-test: is the mean different?
    - Kolmogorov-Smirnov: is the overall distribution shape different?

    A p-value below 0.05 on either test flags possible drift. This is a
    coarse, general-purpose check -- it doesn't know anything about this
    specific series' trend or seasonality, so a "drift" flag on a series
    with an ongoing trend, or right after a normal seasonal transition, is
    a plausible FALSE POSITIVE worth checking by eye rather than an
    automatic alarm. (In practice: a steadily trending series will often
    flag as "drifted" here even when nothing anomalous has happened --
    that's expected, not a bug.)

    Also reports `mean_shift_cohens_d` -- Cohen's d for the mean shift
    (pooled-standard-deviation formula, the standard choice for reporting
    an effect size alongside a Welch's t-test even though the test itself
    doesn't assume equal variances), and the raw `ttest_statistic`/
    `ks_statistic` the two tests are actually built on, which were being
    computed internally and then silently dropped before this fix -- a
    bare p-value doesn't distinguish a barely-significant shift from a
    drastic one, same reasoning behind every other effect size in this
    project. The KS statistic is already itself a natural magnitude (the
    maximum distance between the two windows' empirical CDFs, 0 to 1) and
    needs no further transformation.
    """
    total_needed = recent_window_size + reference_window_size
    if len(df) < total_needed:
        return {
            "error": (
                f"Need at least {total_needed} observations "
                f"(recent_window_size + reference_window_size), got {len(df)}."
            )
        }

    recent = df["value"].iloc[-recent_window_size:].to_numpy(dtype=float)
    reference = df["value"].iloc[-total_needed:-recent_window_size].to_numpy(dtype=float)

    mean_shift_pct = round(100 * (recent.mean() - reference.mean()) / reference.mean(), 3) if reference.mean() != 0 else None
    std_ratio = round(float(recent.std() / reference.std()), 4) if reference.std() != 0 else None

    ttest_stat, ttest_pvalue = ttest_ind(reference, recent, equal_var=False)
    ks_stat, ks_pvalue = ks_2samp(reference, recent)

    n1, n2 = len(reference), len(recent)
    pooled_std = np.sqrt(
        ((n1 - 1) * reference.var(ddof=1) + (n2 - 1) * recent.var(ddof=1)) / (n1 + n2 - 2)
    )
    cohens_d = float((recent.mean() - reference.mean()) / pooled_std) if pooled_std > 0 else None

    drift_detected = bool(ttest_pvalue < 0.05 or ks_pvalue < 0.05)

    return {
        "recent_window_size": recent_window_size,
        "reference_window_size": reference_window_size,
        "mean_shift_pct": mean_shift_pct,
        "std_ratio_recent_over_reference": std_ratio,
        "ttest_statistic": round(float(ttest_stat), 4),
        "ttest_p_value": round(float(ttest_pvalue), 4),
        "mean_shift_cohens_d": round(cohens_d, 4) if cohens_d is not None else None,
        "ks_statistic": round(float(ks_stat), 4),
        "ks_test_p_value": round(float(ks_pvalue), 4),
        "drift_detected": drift_detected,
        "interpretation": (
            (
                f"At least one test flags a significant distributional shift between the "
                f"reference and recent windows (mean shift Cohen's d={round(cohens_d, 2) if cohens_d is not None else 'N/A'}, "
                f"KS statistic={round(float(ks_stat), 3)}). Check by eye whether this lines up with a "
                "known seasonal transition or an ongoing trend (both plausible false "
                "positives for this test) or looks like a genuine regime change unrelated "
                "to trend/seasonality."
            )
            if drift_detected
            else "No significant shift detected between the reference and recent windows."
        ),
    }


def rolling_drift_check(
    df: pd.DataFrame,
    recent_window_size: int = 30,
    reference_window_size: int = 90,
    n_checks: int = 5,
    step_size: Optional[int] = None,
    persistence_threshold_frac: float = 0.5,
) -> dict:
    """Repeats detect_data_drift at n_checks different points walking
    backward through the series (each check's own recent/reference window
    pair, non-overlapping by default), instead of trusting the single
    most-recent split detect_data_drift alone provides. Addresses the same
    "one arbitrary window" fragility ts-forecaster's rolling_origin_backtest
    was built to fix for backtesting: a single recent-vs-reference split
    might have caught an ordinary one-off blip rather than a sustained
    shift, and there was previously no cheap way to tell the difference.

    Unlike rolling_origin_backtest, this is CHEAP per check (a t-test and a
    KS test on numpy arrays, no model fitting), so a larger n_checks costs
    little -- the real constraint is just having enough historical data to
    walk back through.

    Args:
        recent_window_size: Test window size at each check (same meaning
            as detect_data_drift's own parameter).
        reference_window_size: Reference window size at each check.
        n_checks: How many non-overlapping checks to run, walking backward.
        step_size: How far back each successive check's recent window
            starts, relative to the previous one. Defaults to
            recent_window_size (fully non-overlapping recent windows).
        persistence_threshold_frac: Fraction of successful checks that must
            flag drift before this is reported as `persistent_drift`
            (a sustained shift) rather than an isolated flag. Explicit
            parameter, not a hidden constant, same convention as
            recommend_retraining's thresholds.
    """
    step_size = step_size or recent_window_size
    total_needed_per_check = recent_window_size + reference_window_size
    min_required = total_needed_per_check + step_size * (n_checks - 1)
    n = len(df)
    if n < min_required:
        return {
            "error": (
                f"Need at least {min_required} observations for {n_checks} checks "
                f"(recent_window_size + reference_window_size + step_size*(n_checks-1)), got {n}."
            )
        }

    checks = []
    for i in range(n_checks):
        end = n - step_size * i
        df_slice = df.iloc[:end].reset_index(drop=True)
        result = detect_data_drift(df_slice, recent_window_size=recent_window_size, reference_window_size=reference_window_size)
        if "error" in result:
            checks.append({"check_index": i, "error": result["error"]})
            continue
        checks.append(
            {
                "check_index": i,
                "recent_window_end_date": str(df_slice["date"].iloc[-1].date()),
                "drift_detected": result["drift_detected"],
                "mean_shift_cohens_d": result["mean_shift_cohens_d"],
                "ks_statistic": result["ks_statistic"],
            }
        )
    # Chronological order (check 0 above is the most recent; reverse so the
    # report reads oldest-to-newest), same convention as
    # ts-forecaster's rolling_origin_backtest.
    checks.reverse()

    successful = [c for c in checks if "error" not in c]
    n_failed = len(checks) - len(successful)
    if not successful:
        return {"error": f"All {n_checks} checks failed to run.", "checks": checks}

    n_flagged = sum(1 for c in successful if c["drift_detected"])
    frac_flagged = round(n_flagged / len(successful), 4)
    persistent_drift = bool(frac_flagged >= persistence_threshold_frac)

    return {
        "recent_window_size": recent_window_size,
        "reference_window_size": reference_window_size,
        "n_checks": n_checks,
        "step_size": step_size,
        "n_checks_failed": n_failed,
        "checks": checks,
        "n_flagged": n_flagged,
        "frac_flagged": frac_flagged,
        "persistence_threshold_frac": persistence_threshold_frac,
        "persistent_drift": persistent_drift,
        "interpretation": (
            f"{n_flagged}/{len(successful)} rolling checks flagged drift"
            + (f" ({n_failed} check(s) failed to run and were excluded)" if n_failed else "")
            + ". "
            + (
                "Flagged across most checks -- looks like a SUSTAINED shift, not a one-off blip."
                if persistent_drift
                else "Flagged in a minority of checks (or none) -- more consistent with an isolated "
                "blip, a seasonal transition, or noise than a sustained regime change, but still "
                "worth a look at the individual checks below rather than dismissed outright."
            )
        ),
    }


def recommend_retraining(
    mape_now: float,
    mape_backtest: float,
    drift_detected: bool,
    interval_coverage_pct: Optional[float] = None,
    nominal_confidence_pct: Optional[float] = None,
    mape_now_ci_lower: Optional[float] = None,
    mape_now_ci_upper: Optional[float] = None,
    error_degradation_threshold_pct: float = 20.0,
    coverage_miscalibration_threshold_pct: float = 15.0,
) -> dict:
    """Deterministic decision function combining forecast-error degradation
    and data drift into a retrain recommendation. Thresholds are explicit
    parameters, not hidden constants -- adjust them for how conservative
    you want this to be.

    Args:
        mape_now: MAPE of the forecast against real recent observations
            (from compare_forecast_to_actuals).
        mape_backtest: The original backtest MAPE this model achieved in
            Layer 2, for the same model type/settings now deployed.
        drift_detected: Whether detect_data_drift flagged a shift.
        interval_coverage_pct: Empirical prediction interval coverage, if
            available from compare_forecast_to_actuals.
        nominal_confidence_pct: The interval's nominal confidence level,
            if available.
        mape_now_ci_lower: Optional bootstrap CI lower bound on mape_now
            (compare_forecast_to_actuals's mape_pct_ci_lower). If supplied
            alongside mape_now_ci_upper, the implied degradation range
            gets reported too, and flagged if the threshold itself falls
            inside it -- i.e. the degraded/not-degraded verdict is
            sensitive to sampling noise in mape_now, not clear-cut.
            mape_backtest is treated as a fixed constant either way (no
            CI of its own is combined in here).
        mape_now_ci_upper: See mape_now_ci_lower.
        error_degradation_threshold_pct: How much worse (in % relative
            terms) mape_now can be than mape_backtest before it counts as
            "degraded."
        coverage_miscalibration_threshold_pct: How far empirical coverage
            can be from nominal before it counts as "miscalibrated."
    """
    if mape_backtest in (None, 0):
        pct_degradation = None
        performance_degraded = None
        pct_degradation_ci_lower = None
        pct_degradation_ci_upper = None
        degradation_threshold_within_ci = None
    else:
        pct_degradation = round(100 * (mape_now - mape_backtest) / mape_backtest, 2)
        performance_degraded = pct_degradation > error_degradation_threshold_pct

        pct_degradation_ci_lower = pct_degradation_ci_upper = None
        degradation_threshold_within_ci = None
        if mape_now_ci_lower is not None and mape_now_ci_upper is not None:
            pct_degradation_ci_lower = round(100 * (mape_now_ci_lower - mape_backtest) / mape_backtest, 2)
            pct_degradation_ci_upper = round(100 * (mape_now_ci_upper - mape_backtest) / mape_backtest, 2)
            degradation_threshold_within_ci = bool(
                pct_degradation_ci_lower <= error_degradation_threshold_pct <= pct_degradation_ci_upper
            )

    interval_miscalibrated = None
    if interval_coverage_pct is not None and nominal_confidence_pct is not None:
        interval_miscalibrated = abs(interval_coverage_pct - nominal_confidence_pct) > coverage_miscalibration_threshold_pct

    if performance_degraded and drift_detected:
        recommendation = "retrain_now"
        reasoning = (
            "Forecast error has degraded beyond threshold AND the data shows a distributional "
            "shift -- both signals point the same direction. Re-run ts-analyst and ts-forecaster "
            "on the updated series before redeploying."
        )
    elif performance_degraded and not drift_detected:
        recommendation = "investigate"
        reasoning = (
            "Forecast error has degraded beyond threshold but no distribution shift was "
            "detected. Could be a one-off anomaly, a drift test that's insensitive to this "
            "series' pattern, or a genuine slow drift the test isn't picking up. Look at the "
            "matched_points from compare_forecast_to_actuals by eye before deciding."
        )
    elif drift_detected and not performance_degraded:
        recommendation = "monitor_closely"
        reasoning = (
            "The data has shifted, but the forecast is still tracking it acceptably so far -- "
            "not yet a problem, but re-check again soon since degradation may follow."
        )
    else:
        recommendation = "no_action_needed"
        reasoning = "Forecast error is within tolerance and no drift detected."

    if interval_miscalibrated and recommendation == "no_action_needed":
        recommendation = "monitor_closely"
        reasoning += " However, prediction interval coverage is off from nominal -- worth watching even though point-forecast accuracy looks fine."

    if degradation_threshold_within_ci:
        reasoning += (
            f" Note: mape_now's bootstrap CI ([{pct_degradation_ci_lower}%, {pct_degradation_ci_upper}%] implied "
            f"degradation) straddles the {error_degradation_threshold_pct}% threshold -- this "
            "degraded/not-degraded verdict is sensitive to sampling noise in mape_now, not a clear-cut case."
        )

    return {
        "mape_now": mape_now,
        "mape_backtest": mape_backtest,
        "pct_degradation": pct_degradation,
        "pct_degradation_ci_lower": pct_degradation_ci_lower,
        "pct_degradation_ci_upper": pct_degradation_ci_upper,
        "degradation_threshold_within_ci": degradation_threshold_within_ci,
        "performance_degraded": performance_degraded,
        "drift_detected": drift_detected,
        "interval_miscalibrated": interval_miscalibrated,
        "recommendation": recommendation,
        "reasoning": reasoning,
        "thresholds_used": {
            "error_degradation_threshold_pct": error_degradation_threshold_pct,
            "coverage_miscalibration_threshold_pct": coverage_miscalibration_threshold_pct,
        },
    }
