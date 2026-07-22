"""
forecast_tools.py

Layer 3: takes a chosen model type, retrains it on the FULL series (no
holdout -- Layer 2 already told us how well it backtests), and produces a
genuine out-of-sample forecast for dates beyond the last observation.

This is a different job from Layer 2's fit_* functions, which deliberately
withhold the most recent data to score against real values. Here there is
nothing to score against -- the output is a forecast to actually use.
"""

from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy.stats import norm as _norm
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.ensemble import GradientBoostingRegressor


def _future_dates(df: pd.DataFrame, horizon: int) -> pd.DatetimeIndex:
    """Build a date range continuing from the series' last observation, at
    its inferred frequency (falls back to daily if frequency can't be
    inferred, e.g. from an irregular series, OR from a series too short
    to infer from at all -- pd.infer_freq RAISES ValueError, rather than
    returning None, for fewer than 3 dates, so that case needs its own
    guard rather than the `or "D"` fallback alone)."""
    try:
        freq = pd.infer_freq(df["date"]) or "D"
    except ValueError:
        freq = "D"
    return pd.date_range(start=df["date"].iloc[-1], periods=horizon + 1, freq=freq)[1:]


def _format_forecast(dates: Any, values: Any, lower: Any = None, upper: Any = None, cap: int = 60) -> tuple:
    """Turn parallel arrays into a list of {date, forecast, lower?, upper?}
    dicts. If longer than `cap`, truncates to the first/last few and notes
    how many were omitted, so a long horizon doesn't blow up the agent's
    context window.
    """
    n = len(values)
    rows = []
    for i in range(n):
        row = {"date": str(pd.Timestamp(dates[i]).date()), "forecast": round(float(values[i]), 3)}
        if lower is not None:
            row["lower"] = round(float(lower[i]), 3)
        if upper is not None:
            row["upper"] = round(float(upper[i]), 3)
        rows.append(row)

    truncated = False
    if n > cap:
        half = cap // 2
        rows = rows[:half] + [{"note": f"{n - cap} more days omitted for brevity"}] + rows[-half:]
        truncated = True
    return rows, truncated


def _aicc(aic: float, n: int, k: int) -> Optional[float]:
    """Corrected AIC (Hurvich & Tsai, 1989) for small samples -- same
    formula and rationale as ts-forecaster's model_tools.py::_aicc,
    duplicated here (same pattern as _build_lag_features below) so this
    server stays self-contained rather than importing across layers.
    AICc = AIC + 2k(k+1)/(n-k-1); undefined (returns None) when
    n-k-1 <= 0.
    """
    denom = n - k - 1
    if denom <= 0:
        return None
    return round(aic + (2 * k * (k + 1)) / denom, 2)


def _check_forecast_plausibility(df: pd.DataFrame, forecast_values: Any, horizon: int) -> dict:
    """Automates the "does this trajectory look plausible" eyeball check
    that ts-deploy's SKILL.md Step 3 otherwise leaves entirely to the
    agent's judgment. Compares the forecast's implied change (endpoint vs.
    the last observed value) against the empirical distribution of
    horizon-length changes the series has actually made historically, and
    flags whether the forecast ever leaves the historical min/max range
    entirely.

    This is deliberately NOT a hypothesis test -- there's no null
    distribution to test against, only "has the series done something
    like this before." A large z-score/percentile-rank here means the
    forecast is unusual relative to history, not that it's wrong; a
    genuine regime change (new promotion, new market conditions) can
    legitimately produce an "implausible" forecast that's actually
    correct. Treat this as a prompt for scrutiny, not a verdict.
    """
    values = np.asarray(df["value"].values, dtype=float)
    forecast_values = np.asarray(forecast_values, dtype=float)
    n = len(values)
    last_observed = float(values[-1])
    forecast_endpoint = float(forecast_values[-1])
    endpoint_change = forecast_endpoint - last_observed

    result: dict = {
        "forecast_endpoint_change": round(endpoint_change, 4),
        "historical_min": round(float(values.min()), 4),
        "historical_max": round(float(values.max()), 4),
        "forecast_min": round(float(forecast_values.min()), 4),
        "forecast_max": round(float(forecast_values.max()), 4),
        "goes_below_historical_min": bool(forecast_values.min() < values.min()),
        "goes_above_historical_max": bool(forecast_values.max() > values.max()),
    }

    if n <= horizon:
        result.update(
            {
                "historical_horizon_change_mean": None,
                "historical_horizon_change_std": None,
                "endpoint_change_z_score": None,
                "endpoint_change_percentile_rank": None,
                "is_extreme_relative_to_history": None,
                "interpretation": (
                    f"Not enough history ({n} rows) to compare against {horizon}-step historical "
                    "changes -- skipping the statistical plausibility check; use judgment instead."
                ),
            }
        )
        return result

    historical_changes = values[horizon:] - values[:-horizon]
    hist_mean = float(np.mean(historical_changes))
    hist_std = float(np.std(historical_changes, ddof=1)) if len(historical_changes) > 1 else 0.0
    result["historical_horizon_change_mean"] = round(hist_mean, 4)
    result["historical_horizon_change_std"] = round(hist_std, 4)

    if hist_std <= 1e-8:
        result.update(
            {
                "endpoint_change_z_score": None,
                "endpoint_change_percentile_rank": None,
                "is_extreme_relative_to_history": None,
                "interpretation": (
                    "Historical horizon-length changes have ~zero variance -- can't meaningfully "
                    "compare the forecast against them."
                ),
            }
        )
        return result

    z = (endpoint_change - hist_mean) / hist_std
    percentile_rank = round(100 * float(np.mean(historical_changes <= endpoint_change)), 2)
    is_extreme = bool(abs(z) > 2.5)
    result["endpoint_change_z_score"] = round(float(z), 4)
    result["endpoint_change_percentile_rank"] = percentile_rank
    result["is_extreme_relative_to_history"] = is_extreme
    result["interpretation"] = (
        f"The forecast implies a change of {round(endpoint_change, 2)} over this horizon, which is "
        f"{round(abs(z), 2)} standard deviations {'above' if z > 0 else 'below'} the historical "
        f"average {horizon}-step change ({round(hist_mean, 2)} ± {round(hist_std, 2)}) -- "
        + (
            "an unusually large move relative to what this series has done before; treat with extra "
            "scrutiny unless there's a specific reason to expect it (known promotion, seasonality "
            "the model may have missed, etc.)."
            if is_extreme
            else "within the range of moves this series has made before."
        )
    )
    return result


def _fit_naive_values(df: pd.DataFrame, horizon: int, seasonal_period: int, method: str, confidence_level: float) -> dict:
    dates = _future_dates(df, horizon)
    last_value = df["value"].iloc[-1]
    values_arr = df["value"].to_numpy(dtype=float)

    if method == "seasonal_naive" and len(df) >= seasonal_period:
        tail = df["value"].iloc[-seasonal_period:].to_numpy(dtype=float)
        reps = int(np.ceil(horizon / seasonal_period))
        point = np.tile(tail, reps)[:horizon]
        # In-sample SEASONAL differences (y_t - y_{t-m}) are this method's own
        # one-step-ahead residuals -- their std is the textbook basis for a
        # seasonal-naive prediction interval (Hyndman & Athanasopoulos).
        residuals = values_arr[seasonal_period:] - values_arr[:-seasonal_period]
        h = np.arange(1, horizon + 1)
        # Widens only at each COMPLETE additional seasonal cycle, not every
        # step -- same forecast is repeated m steps at a time, so steps
        # within one cycle share the same uncertainty.
        cycles = np.floor((h - 1) / seasonal_period) + 1
    else:
        point = np.full(horizon, last_value)
        method = "naive"
        # In-sample one-step differences are the flat-naive method's own
        # residuals (a naive forecast IS a random-walk-with-no-drift model).
        residuals = np.diff(values_arr)
        h = np.arange(1, horizon + 1)
        cycles = h

    lower = upper = None
    if len(residuals) >= 2:
        sigma = float(np.std(residuals, ddof=1))
        alpha = 1 - confidence_level
        z = float(_norm.ppf(1 - alpha / 2))
        sigma_h = sigma * np.sqrt(cycles)
        lower = point - z * sigma_h
        upper = point + z * sigma_h
        interval_note = (
            f"{int(confidence_level * 100)}% analytic interval from the in-sample "
            f"{'seasonal-difference' if method == 'seasonal_naive' else 'one-step-difference'} "
            "residual standard deviation, widening as the horizon grows (textbook naive-forecast "
            "interval, Hyndman & Athanasopoulos -- not simulation-based)."
        )
    else:
        interval_note = "Point forecast only -- not enough history to estimate residual variance for an interval."

    return {"point": point, "lower": lower, "upper": upper, "dates": dates, "method": method, "interval_note": interval_note}


def forecast_naive(
    df: pd.DataFrame, horizon: int = 30, seasonal_period: int = 7, method: str = "seasonal_naive", confidence_level: float = 0.95
) -> dict:
    """Extend the series with a trivial baseline forecast: either flat
    (repeat the last value) or seasonal (repeat the last full seasonal
    cycle). Useful as a sanity-check floor alongside a real model's
    forecast, same role naive baselines played in Layer 2's backtest.

    Now includes an analytic prediction interval (see _fit_naive_values):
    built from the in-sample residual standard deviation of this same
    naive method (one-step differences for flat naive, seasonal
    differences for seasonal naive), widening with the square root of
    elapsed steps/cycles -- the standard textbook interval for a
    random-walk-style forecast, not simulation-based like ETS's.
    """
    raw = _fit_naive_values(df, horizon, seasonal_period, method, confidence_level)
    rows, truncated = _format_forecast(raw["dates"], raw["point"], raw["lower"], raw["upper"])
    return {
        "model": f"naive ({raw['method']})",
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": raw["interval_note"],
        "plausibility_check": _check_forecast_plausibility(df, raw["point"], horizon),
    }


def _fit_ets_values(
    df: pd.DataFrame,
    horizon: int,
    seasonal_period: int,
    trend: str,
    seasonal: str,
    damped_trend: bool,
    confidence_level: float,
    n_simulations: int,
) -> dict:
    model = ExponentialSmoothing(
        df["value"], trend=trend, seasonal=seasonal, seasonal_periods=seasonal_period, damped_trend=damped_trend
    )
    fit = model.fit()

    dates = _future_dates(df, horizon)
    point_forecast = fit.forecast(horizon).values

    lower = upper = None
    alpha = 1 - confidence_level
    try:
        sims = fit.simulate(nsimulations=horizon, repetitions=n_simulations, error="add")
        lower = sims.quantile(alpha / 2, axis=1).values
        upper = sims.quantile(1 - alpha / 2, axis=1).values
        interval_note = f"{int(confidence_level * 100)}% interval from {n_simulations} simulated future paths."
    except Exception as exc:
        interval_note = f"Point forecast only -- simulation-based interval failed for this configuration ({exc})."

    return {
        "point": point_forecast,
        "lower": lower,
        "upper": upper,
        "dates": dates,
        "aic": float(fit.aic),
        "aicc": _aicc(float(fit.aic), len(df), len(fit.params)),
        "interval_note": interval_note,
    }


def forecast_ets(
    df: pd.DataFrame,
    horizon: int = 30,
    seasonal_period: int = 7,
    trend: str = "add",
    seasonal: str = "add",
    damped_trend: bool = False,
    confidence_level: float = 0.95,
    n_simulations: int = 500,
) -> dict:
    """Retrain Holt-Winters (ETS) on the FULL series and forecast `horizon`
    steps beyond the last observation. Prediction intervals are derived by
    simulating `n_simulations` future paths and taking percentiles -- if
    simulation fails for this parameter combination, falls back to a
    point-forecast-only result rather than erroring out. `aicc` is the
    small-sample-corrected AIC (see _aicc); mostly useful here as a
    diagnostic against the model actually recommended by ts-forecaster's
    fit_ets, since this refit uses the FULL series (different n) so the
    two aicc values won't match exactly.
    """
    raw = _fit_ets_values(df, horizon, seasonal_period, trend, seasonal, damped_trend, confidence_level, n_simulations)
    rows, truncated = _format_forecast(raw["dates"], raw["point"], raw["lower"], raw["upper"])
    return {
        "model": "ETS (Holt-Winters)",
        "params": {"trend": trend, "seasonal": seasonal, "seasonal_period": seasonal_period, "damped_trend": damped_trend},
        "aic": round(raw["aic"], 2),
        "aicc": raw["aicc"],
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": raw["interval_note"],
        "plausibility_check": _check_forecast_plausibility(df, raw["point"], horizon),
    }


def _fit_sarima_values(
    df: pd.DataFrame, horizon: int, order: Optional[list], seasonal_order: Optional[list], confidence_level: float
) -> dict:
    order_tuple = tuple(order) if order else (1, 1, 1)
    seasonal_order_tuple = tuple(seasonal_order) if seasonal_order else (1, 1, 1, 7)

    # Single-column DataFrame, not a Series -- avoids statsmodels' deprecated
    # in-place ndarray.shape= reshape (NumPy 2.5+ DeprecationWarning), which
    # only triggers for 1-D endog. See forecaster/model_tools.py::fit_sarima.
    model = SARIMAX(
        df[["value"]], order=order_tuple, seasonal_order=seasonal_order_tuple, enforce_stationarity=False, enforce_invertibility=False
    )
    fit = model.fit(disp=False)

    dates = _future_dates(df, horizon)
    prediction = fit.get_forecast(steps=horizon)
    point_forecast = prediction.predicted_mean.values
    ci = prediction.conf_int(alpha=1 - confidence_level)
    lower, upper = ci.iloc[:, 0].values, ci.iloc[:, 1].values

    return {
        "point": point_forecast,
        "lower": lower,
        "upper": upper,
        "dates": dates,
        "order": order_tuple,
        "seasonal_order": seasonal_order_tuple,
        "aic": float(fit.aic),
        "aicc": _aicc(float(fit.aic), len(df), len(fit.params)),
        "bic": float(fit.bic),
    }


def forecast_sarima(
    df: pd.DataFrame,
    horizon: int = 30,
    order: Optional[list] = None,
    seasonal_order: Optional[list] = None,
    confidence_level: float = 0.95,
) -> dict:
    """Retrain SARIMA on the FULL series and forecast `horizon` steps
    beyond the last observation, with an analytic confidence interval from
    the state-space model (no simulation needed -- SARIMAX provides this
    directly, unlike Holt-Winters). `aicc` is the small-sample-corrected
    AIC (see _aicc), computed against this refit on the full series (so it
    won't numerically match ts-forecaster's fit_sarima aicc, which is
    computed on the training split only).
    """
    raw = _fit_sarima_values(df, horizon, order, seasonal_order, confidence_level)
    rows, truncated = _format_forecast(raw["dates"], raw["point"], raw["lower"], raw["upper"])
    return {
        "model": "SARIMA",
        "params": {"order": list(raw["order"]), "seasonal_order": list(raw["seasonal_order"])},
        "aic": round(raw["aic"], 2),
        "aicc": raw["aicc"],
        "bic": round(raw["bic"], 2),
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": f"{int(confidence_level * 100)}% analytic confidence interval from the state-space model.",
        "plausibility_check": _check_forecast_plausibility(df, raw["point"], horizon),
    }


def _build_lag_features(df: pd.DataFrame, lags: list) -> pd.DataFrame:
    """Same feature construction as Layer 2's model_tools.py, duplicated
    here so this server stays self-contained. Preserves original row
    position in `time_index` (i.e. does NOT reset to 0 after dropna), so
    future time_index values continue naturally from len(df)."""
    feat = df.copy()
    for lag in lags:
        feat[f"lag_{lag}"] = feat["value"].shift(lag)
    feat["day_of_week"] = feat["date"].dt.dayofweek
    feat["month"] = feat["date"].dt.month
    feat["time_index"] = np.arange(len(feat))
    feat = feat.dropna().reset_index(drop=True)
    return feat


def _fit_gbt_values(
    df: pd.DataFrame,
    horizon: int,
    lags: Optional[list],
    n_estimators: int,
    max_depth: int,
    learning_rate: float,
    confidence_level: float,
    n_bootstrap: int = 100,
    seed: int = 42,
) -> dict:
    lags = lags or [1, 7, 14]
    feat = _build_lag_features(df, lags)
    feature_cols = [f"lag_{lag}" for lag in lags] + ["day_of_week", "month", "time_index"]
    alpha = 1 - confidence_level

    point_model = GradientBoostingRegressor(
        n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate, random_state=42
    )
    point_model.fit(feat[feature_cols], feat["value"])

    # Two extra models trained with sklearn's built-in quantile loss give an
    # approximate prediction interval, which point_model alone can't -- see
    # forecast_gradient_boosted_trees's docstring/caveat for what this
    # interval does and doesn't account for.
    lower_model = GradientBoostingRegressor(
        loss="quantile", alpha=alpha / 2,
        n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate, random_state=42,
    )
    lower_model.fit(feat[feature_cols], feat["value"])

    upper_model = GradientBoostingRegressor(
        loss="quantile", alpha=1 - alpha / 2,
        n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate, random_state=42,
    )
    upper_model.fit(feat[feature_cols], feat["value"])

    history = df[["date", "value"]].copy().reset_index(drop=True)
    future_dates = _future_dates(df, horizon)
    point_preds, lower_preds, upper_preds = [], [], []

    for current_date in future_dates:
        row = {f"lag_{lag}": history["value"].iloc[-lag] for lag in lags}
        row["day_of_week"] = pd.Timestamp(current_date).dayofweek
        row["month"] = pd.Timestamp(current_date).month
        row["time_index"] = len(history)

        x_next = pd.DataFrame([row])[feature_cols]
        point_pred = float(point_model.predict(x_next)[0])
        lower_pred = float(lower_model.predict(x_next)[0])
        upper_pred = float(upper_model.predict(x_next)[0])

        point_preds.append(point_pred)
        lower_preds.append(lower_pred)
        upper_preds.append(upper_pred)

        # Subsequent lag features always follow the POINT model's own
        # trajectory, not the quantile models' -- one consistent recursive
        # path instead of three diverging ones.
        history = pd.concat(
            [history, pd.DataFrame({"date": [current_date], "value": [point_pred]})], ignore_index=True
        )

    point_arr = np.array(point_preds)
    lower_arr = np.array(lower_preds)
    upper_arr = np.array(upper_preds)
    # Independently-fit quantile models can cross (lower > upper),
    # especially with limited data -- guard against a physically
    # nonsensical interval before returning it.
    lower_arr, upper_arr = np.minimum(lower_arr, upper_arr), np.maximum(lower_arr, upper_arr)
    # The point model is ALSO independently fit (squared-error loss, not
    # quantile loss) -- nothing mathematically ties it to the quantile
    # models, so it can legitimately fall outside their own interval.
    # Same guard-don't-refit philosophy as the crossing fix above.
    lower_arr, upper_arr = np.minimum(lower_arr, point_arr), np.maximum(upper_arr, point_arr)

    point_importances = {
        col: round(float(imp), 4) for col, imp in zip(feature_cols, point_model.feature_importances_)
    }

    # Bootstrap CI for feature importances: refit on resampled TRAINING ROWS
    # (not resampled residuals/errors like compute_metrics_with_ci elsewhere
    # in this toolkit -- there's no "error" to resample here, importance is
    # a property of the fitted model itself, so the resampling has to act on
    # what the model is fit ON). Each resample is a full GradientBoosting fit
    # at the SAME n_estimators/max_depth/learning_rate as the point model --
    # this is real, not cheap: n_bootstrap extra full model fits on top of
    # the three above, unlike the rest of this toolkit's bootstrap CIs (which
    # resample a precomputed metric formula, not refit a model each time).
    # n_bootstrap=0 is a legitimate, cheap opt-out (e.g. forecast_ensemble's
    # internal GBT fit uses it -- ensemble results never surface per-model
    # feature importances at all, so paying for the CI there is pure waste).
    importances: dict[str, dict[str, Any]]
    if n_bootstrap > 0:
        rng = np.random.default_rng(seed)
        n_rows = len(feat)
        boot_samples: dict[str, list[float]] = {col: [] for col in feature_cols}
        for _ in range(n_bootstrap):
            idx = rng.integers(0, n_rows, size=n_rows)
            boot_model = GradientBoostingRegressor(
                n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate, random_state=42
            )
            boot_model.fit(feat[feature_cols].iloc[idx], feat["value"].iloc[idx])
            for col, imp in zip(feature_cols, boot_model.feature_importances_):
                boot_samples[col].append(imp)

        importances = {}
        for col in feature_cols:
            samples = np.asarray(boot_samples[col], dtype=float)
            importances[col] = {
                "importance": point_importances[col],
                "ci_lower": round(float(np.percentile(samples, 100 * alpha / 2)), 4),
                "ci_upper": round(float(np.percentile(samples, 100 * (1 - alpha / 2))), 4),
            }
    else:
        importances = {col: {"importance": point_importances[col], "ci_lower": None, "ci_upper": None} for col in feature_cols}

    return {
        "point": np.array(point_preds),
        "lower": lower_arr,
        "upper": upper_arr,
        "dates": future_dates,
        "lags": lags,
        "feature_importances": importances,
        "feature_importance_ci_n_bootstrap": n_bootstrap,
        "feature_importance_ci_confidence_level": confidence_level,
        "interval_note": (
            f"{int(confidence_level * 100)}% interval from separate quantile-regression models "
            f"(loss='quantile', alpha={round(alpha / 2, 4)} and {round(1 - alpha / 2, 4)}) trained "
            "alongside the point-forecast model. Approximate: unlike SARIMA's analytic interval or "
            "ETS's simulated one, it doesn't explicitly grow with the compounding recursive "
            "uncertainty of longer horizons, and independently-fit quantile models can occasionally "
            "cross (guarded against above)."
        ),
    }


def forecast_gradient_boosted_trees(
    df: pd.DataFrame,
    horizon: int = 30,
    lags: Optional[list] = None,
    n_estimators: int = 200,
    max_depth: int = 3,
    learning_rate: float = 0.05,
    confidence_level: float = 0.95,
    n_bootstrap: int = 100,
    seed: int = 42,
) -> dict:
    """Retrain gradient-boosted trees on lag + calendar features using the
    FULL series, then forecast `horizon` steps ahead RECURSIVELY: each
    predicted value is fed back in as a lag feature for subsequent steps.

    This is a materially different (and riskier) evaluation setting than
    Layer 2's one-step-ahead backtest, which used TRUE lagged values at
    every point. Here, errors can compound over the horizon since later
    predictions depend on earlier ones being roughly correct.

    A prediction interval is available (via two extra quantile-regression
    models, see _fit_gbt_values) but is approximate -- it does not itself
    account for the recursive compounding risk described above and in the
    `caveat` field.

    `feature_importances` is now `{col: {importance, ci_lower, ci_upper}}`,
    not a bare `{col: importance}` float -- a SHAPE CHANGE, not just an
    added field, same pattern as ts-analyst's earlier ACF/anomaly-detector
    upgrades. The CI comes from refitting on `n_bootstrap` resamples of the
    TRAINING ROWS (not resampled errors -- there's no "error" to resample
    for a feature-importance question, only what the model was fit on).
    This is expensive: `n_bootstrap` extra full model fits on top of the
    three already required for the point forecast and its interval --
    fitting this tool now costs roughly `3 + n_bootstrap` model fits total,
    not 3. Lower `n_bootstrap` (or `n_estimators`) if that cost matters for
    your use case; both are honest quality/speed tradeoffs, not defaults
    to leave untouched by convention.
    """
    raw = _fit_gbt_values(df, horizon, lags, n_estimators, max_depth, learning_rate, confidence_level, n_bootstrap, seed)
    rows, truncated = _format_forecast(raw["dates"], raw["point"], raw["lower"], raw["upper"])

    return {
        "model": "Gradient Boosted Trees (recursive multi-step forecast)",
        "params": {"lags": raw["lags"], "n_estimators": n_estimators, "max_depth": max_depth, "learning_rate": learning_rate},
        "feature_importances": raw["feature_importances"],
        "feature_importance_ci_n_bootstrap": raw["feature_importance_ci_n_bootstrap"],
        "feature_importance_ci_confidence_level": raw["feature_importance_ci_confidence_level"],
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": raw["interval_note"],
        "plausibility_check": _check_forecast_plausibility(df, raw["point"], horizon),
        "caveat": (
            "This is a RECURSIVE multi-step forecast: each prediction feeds back in as a lag "
            "feature for later steps, so errors can compound as the horizon grows. This "
            "compounding risk did not apply to Layer 2's evaluation of this same model type, "
            "which used true lagged values throughout -- treat longer horizons here with more "
            "skepticism than the equivalent SARIMA/ETS forecast. The interval above is quantile- "
            "regression-based, not derived from this same recursive process, so treat it as a "
            "rough guide, not a rigorous bound on the compounding risk specifically."
        ),
    }


_ENSEMBLE_MODEL_TYPES = ("naive", "ets", "sarima", "gbt")


def forecast_ensemble(
    df: pd.DataFrame,
    model_types: list,
    horizon: int = 30,
    weights: Optional[list] = None,
    model_params: Optional[dict] = None,
    confidence_level: float = 0.95,
) -> dict:
    """Combine two or more of this layer's own forecasts into a single
    weighted forecast. This is the tool for the question "what should I
    actually deploy if two backtest-validated candidates are both
    reasonable" -- ts-forecaster deliberately stops at evaluating
    candidates individually (see its own Next Steps), because producing a
    forecast to use, rather than judging candidates, is this layer's job.

    Requires at least 2 entries in `model_types`, each one of "naive",
    "ets", "sarima", "gbt". `weights` defaults to equal weighting; if
    supplied, must be the same length as `model_types` and non-negative
    (normalized to sum to 1 internally regardless of scale, so passing
    raw inverse-backtest-error values from ts-forecaster's
    backtest_metrics works directly without pre-normalizing them
    yourself). `model_params` optionally overrides per-model settings,
    e.g. {"sarima": {"order": [1,1,1], "seasonal_order": [1,1,1,7]},
    "ets": {"seasonal_period": 7}} -- omit a model_type's key to use its
    own defaults.

    The combined point forecast is a straightforward weighted average at
    each future date. The combined interval, when reported, is a
    VARIANCE combination (each component's own interval width is
    converted to an implied standard deviation, combined via
    sqrt(sum(w_i^2 * sigma_i^2)) under an INDEPENDENCE assumption between
    components, then rebuilt around the weighted point forecast) -- more
    principled than a plain bound average, but the independence
    assumption is optimistic (every component is fit on the SAME series
    and shares real error structure), so treat it as a lower bound on the
    ensemble's true uncertainty; see `interval_note`. It CAN come out
    narrower than any single component's own interval -- that's the
    expected effect of combining independent estimates, not a bug. If any
    included model contributes no interval of its own (e.g. naive with
    too little history to estimate residual variance, or ETS after a
    failed simulation), the ensemble reports no combined interval at all
    rather than silently dropping that model's weight from a partial
    combination.
    """
    if not model_types or len(model_types) < 2:
        return {"error": f"Need at least 2 model_types to ensemble, got {model_types!r}."}
    unknown = sorted(set(model_types) - set(_ENSEMBLE_MODEL_TYPES))
    if unknown:
        return {"error": f"Unknown model_types {unknown}; must be from {list(_ENSEMBLE_MODEL_TYPES)}."}

    if weights is None:
        weights = [1.0] * len(model_types)
    if len(weights) != len(model_types):
        return {"error": f"weights (len {len(weights)}) must match model_types (len {len(model_types)})."}
    if any(w < 0 for w in weights) or sum(weights) <= 0:
        return {"error": "weights must be non-negative and sum to a positive number."}
    weights = [w / sum(weights) for w in weights]

    model_params = model_params or {}
    dates = _future_dates(df, horizon)

    components = []
    point_forecasts = []
    interval_pairs = []

    for model_type, weight in zip(model_types, weights):
        params = dict(model_params.get(model_type, {}))
        try:
            if model_type == "naive":
                raw = _fit_naive_values(
                    df, horizon, params.get("seasonal_period", 7), params.get("method", "seasonal_naive"), confidence_level
                )
                point, lower, upper = raw["point"], raw["lower"], raw["upper"]
                label = f"naive ({raw['method']})"
            elif model_type == "ets":
                raw = _fit_ets_values(
                    df, horizon,
                    params.get("seasonal_period", 7),
                    params.get("trend", "add"),
                    params.get("seasonal", "add"),
                    params.get("damped_trend", False),
                    confidence_level,
                    params.get("n_simulations", 500),
                )
                point, lower, upper = raw["point"], raw["lower"], raw["upper"]
                label = "ETS (Holt-Winters)"
            elif model_type == "sarima":
                raw = _fit_sarima_values(df, horizon, params.get("order"), params.get("seasonal_order"), confidence_level)
                point, lower, upper = raw["point"], raw["lower"], raw["upper"]
                label = "SARIMA"
            else:  # gbt
                raw = _fit_gbt_values(
                    df, horizon,
                    params.get("lags"),
                    params.get("n_estimators", 200),
                    params.get("max_depth", 3),
                    params.get("learning_rate", 0.05),
                    confidence_level,
                    n_bootstrap=0,  # ensemble results don't surface feature_importances at all
                )
                point, lower, upper = raw["point"], raw["lower"], raw["upper"]
                label = "Gradient Boosted Trees (recursive)"
        except Exception as exc:
            return {"error": f"{model_type} failed to fit: {exc}"}

        point_forecasts.append(np.asarray(point, dtype=float))
        interval_pairs.append((lower, upper) if lower is not None and upper is not None else None)
        components.append(
            {"model_type": model_type, "model": label, "weight": round(weight, 4), "has_interval": lower is not None}
        )

    weighted_point = np.zeros(horizon)
    for values, weight in zip(point_forecasts, weights):
        weighted_point += weight * values

    lower = upper = None
    if all(iv is not None for iv in interval_pairs):
        # Variance combination, not a bound average: convert each component's
        # own interval half-width back into an implied standard deviation
        # (assumes each component's interval is roughly symmetric around its
        # own point forecast -- true for naive/SARIMA/ETS, approximately true
        # for GBT's quantile-regression interval), then combine under an
        # INDEPENDENCE assumption: var_combined = sum(w_i^2 * sigma_i^2).
        # This is a real, standard variance-combination technique -- but the
        # independence assumption is almost certainly optimistic, since every
        # component was fit on the SAME series and will share some error
        # structure. Treat the result as a lower bound on the ensemble's true
        # uncertainty, not a precise one; see interval_note.
        alpha = 1 - confidence_level
        z = float(_norm.ppf(1 - alpha / 2))
        combined_variance = np.zeros(horizon)
        non_null_pairs = [iv for iv in interval_pairs if iv is not None]
        for (lo, up), weight in zip(non_null_pairs, weights):
            sigma_i = (np.asarray(up, dtype=float) - np.asarray(lo, dtype=float)) / (2 * z)
            combined_variance += (weight**2) * (sigma_i**2)
        combined_sigma = np.sqrt(combined_variance)
        lower = weighted_point - z * combined_sigma
        upper = weighted_point + z * combined_sigma
        interval_note = (
            f"{int(confidence_level * 100)}% combined interval assuming component models' forecast "
            "errors are INDEPENDENT: each component's own interval width is converted to an implied "
            "standard deviation, combined via sqrt(sum(w_i^2 * sigma_i^2)), then rebuilt around the "
            "weighted point forecast. A real variance-combination technique, not a bound average -- "
            "but the independence assumption is almost certainly optimistic (every component was fit "
            "on the SAME series and shares some error structure), so treat this as a LOWER BOUND on "
            "the ensemble's true uncertainty, not a precise one. Can come out NARROWER than any single "
            "component's own interval -- that's the expected effect of combining independent "
            "estimates, not a bug."
        )
    else:
        missing = [c["model_type"] for c in components if not c["has_interval"]]
        interval_note = f"No combined interval -- {missing} contributed no prediction interval of its own."

    rows, truncated = _format_forecast(dates, weighted_point, lower, upper)

    result = {
        "model": f"Ensemble ({' + '.join(model_types)})",
        "components": components,
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": interval_note,
        "plausibility_check": _check_forecast_plausibility(df, weighted_point, horizon),
    }
    if "gbt" in model_types:
        result["caveat"] = (
            "Includes gradient-boosted trees, whose own forecast is RECURSIVE and can compound "
            "error over the horizon -- that risk carries into this weighted combination too, "
            "diluted but not eliminated by the other models' weight."
        )
    return result
