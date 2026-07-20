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

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, ttest_ind


def compute_metrics(y_true, y_pred) -> dict:
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


def compare_forecast_to_actuals(
    forecast: list,
    df: pd.DataFrame,
    confidence_level: float = 0.95,
) -> dict:
    """Match a previously produced forecast (the list of {date, forecast,
    lower?, upper?} dicts a ts-deploy tool returned) against real observed
    values now present in the updated series, and report:
    - error metrics over whatever portion of the horizon has actually
      elapsed
    - prediction interval coverage, if the forecast included one: what
      fraction of realized actuals actually fell inside their interval,
      vs. the nominal confidence level.
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
    metrics = compute_metrics(y_true, y_pred)

    coverage_result = {"interval_available": False}
    has_intervals = all(m["lower"] is not None and m["upper"] is not None for m in matched)
    if has_intervals:
        within = sum(1 for m in matched if m["lower"] <= m["actual"] <= m["upper"])
        coverage_pct = round(100 * within / len(matched), 2)
        nominal_pct = round(confidence_level * 100, 2)
        coverage_result = {
            "interval_available": True,
            "empirical_coverage_pct": coverage_pct,
            "nominal_confidence_pct": nominal_pct,
            "well_calibrated": bool(abs(coverage_pct - nominal_pct) <= 15),
            "interpretation": (
                f"{coverage_pct}% of realized actuals fell within their prediction interval, "
                f"vs. a nominal {nominal_pct}%. "
                + (
                    "Reasonably close to nominal -- interval looks calibrated."
                    if abs(coverage_pct - nominal_pct) <= 15
                    else "Notably off from nominal -- the interval is likely too narrow (if "
                    "coverage is low) or too wide (if coverage is much higher than nominal), "
                    "and shouldn't be trusted at face value."
                )
            ),
        }

    return {
        "n_dates_compared": len(matched),
        "date_range_compared": [matched[0]["date"], matched[-1]["date"]],
        "backtest_style_metrics": metrics,
        "interval_coverage": coverage_result,
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
    """
    total_needed = recent_window_size + reference_window_size
    if len(df) < total_needed:
        return {
            "error": (
                f"Need at least {total_needed} observations "
                f"(recent_window_size + reference_window_size), got {len(df)}."
            )
        }

    recent = df["value"].iloc[-recent_window_size:].values
    reference = df["value"].iloc[-total_needed:-recent_window_size].values

    mean_shift_pct = round(100 * (recent.mean() - reference.mean()) / reference.mean(), 3) if reference.mean() != 0 else None
    std_ratio = round(float(recent.std() / reference.std()), 4) if reference.std() != 0 else None

    ttest_stat, ttest_pvalue = ttest_ind(reference, recent, equal_var=False)
    ks_stat, ks_pvalue = ks_2samp(reference, recent)

    drift_detected = bool(ttest_pvalue < 0.05 or ks_pvalue < 0.05)

    return {
        "recent_window_size": recent_window_size,
        "reference_window_size": reference_window_size,
        "mean_shift_pct": mean_shift_pct,
        "std_ratio_recent_over_reference": std_ratio,
        "ttest_p_value": round(float(ttest_pvalue), 4),
        "ks_test_p_value": round(float(ks_pvalue), 4),
        "drift_detected": drift_detected,
        "interpretation": (
            (
                "At least one test flags a significant distributional shift between the "
                "reference and recent windows. Check by eye whether this lines up with a "
                "known seasonal transition or an ongoing trend (both plausible false "
                "positives for this test) or looks like a genuine regime change unrelated "
                "to trend/seasonality."
            )
            if drift_detected
            else "No significant shift detected between the reference and recent windows."
        ),
    }


def recommend_retraining(
    mape_now: float,
    mape_backtest: float,
    drift_detected: bool,
    interval_coverage_pct: float = None,
    nominal_confidence_pct: float = None,
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
        error_degradation_threshold_pct: How much worse (in % relative
            terms) mape_now can be than mape_backtest before it counts as
            "degraded."
        coverage_miscalibration_threshold_pct: How far empirical coverage
            can be from nominal before it counts as "miscalibrated."
    """
    if mape_backtest in (None, 0):
        pct_degradation = None
        performance_degraded = None
    else:
        pct_degradation = round(100 * (mape_now - mape_backtest) / mape_backtest, 2)
        performance_degraded = pct_degradation > error_degradation_threshold_pct

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

    return {
        "mape_now": mape_now,
        "mape_backtest": mape_backtest,
        "pct_degradation": pct_degradation,
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
