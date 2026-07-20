"""
forecast_tools.py

Layer 3: takes a chosen model type, retrains it on the FULL series (no
holdout -- Layer 2 already told us how well it backtests), and produces a
genuine out-of-sample forecast for dates beyond the last observation.

This is a different job from Layer 2's fit_* functions, which deliberately
withhold the most recent data to score against real values. Here there is
nothing to score against -- the output is a forecast to actually use.
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.ensemble import GradientBoostingRegressor


def _future_dates(df: pd.DataFrame, horizon: int) -> pd.DatetimeIndex:
    """Build a date range continuing from the series' last observation, at
    its inferred frequency (falls back to daily if frequency can't be
    inferred, e.g. from an irregular series)."""
    freq = pd.infer_freq(df["date"]) or "D"
    return pd.date_range(start=df["date"].iloc[-1], periods=horizon + 1, freq=freq)[1:]


def _format_forecast(dates, values, lower=None, upper=None, cap: int = 60):
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


def forecast_naive(df: pd.DataFrame, horizon: int = 30, seasonal_period: int = 7, method: str = "seasonal_naive") -> dict:
    """Extend the series with a trivial baseline forecast: either flat
    (repeat the last value) or seasonal (repeat the last full seasonal
    cycle). Useful as a sanity-check floor alongside a real model's
    forecast, same role naive baselines played in Layer 2's backtest.
    """
    dates = _future_dates(df, horizon)
    last_value = df["value"].iloc[-1]

    if method == "seasonal_naive" and len(df) >= seasonal_period:
        tail = df["value"].iloc[-seasonal_period:].values
        reps = int(np.ceil(horizon / seasonal_period))
        values = np.tile(tail, reps)[:horizon]
    else:
        values = np.full(horizon, last_value)
        method = "naive"

    rows, truncated = _format_forecast(dates, values)
    return {
        "model": f"naive ({method})",
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": "No prediction interval for naive baselines -- point forecast only.",
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
    point-forecast-only result rather than erroring out.
    """
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

    rows, truncated = _format_forecast(dates, point_forecast, lower, upper)
    return {
        "model": "ETS (Holt-Winters)",
        "params": {"trend": trend, "seasonal": seasonal, "seasonal_period": seasonal_period, "damped_trend": damped_trend},
        "aic": round(float(fit.aic), 2),
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": interval_note,
    }


def forecast_sarima(
    df: pd.DataFrame,
    horizon: int = 30,
    order: list = None,
    seasonal_order: list = None,
    confidence_level: float = 0.95,
) -> dict:
    """Retrain SARIMA on the FULL series and forecast `horizon` steps
    beyond the last observation, with an analytic confidence interval from
    the state-space model (no simulation needed -- SARIMAX provides this
    directly, unlike Holt-Winters).
    """
    order = tuple(order) if order else (1, 1, 1)
    seasonal_order = tuple(seasonal_order) if seasonal_order else (1, 1, 1, 7)

    # Single-column DataFrame, not a Series -- avoids statsmodels' deprecated
    # in-place ndarray.shape= reshape (NumPy 2.5+ DeprecationWarning), which
    # only triggers for 1-D endog. See forecaster/model_tools.py::fit_sarima.
    model = SARIMAX(
        df[["value"]], order=order, seasonal_order=seasonal_order, enforce_stationarity=False, enforce_invertibility=False
    )
    fit = model.fit(disp=False)

    dates = _future_dates(df, horizon)
    prediction = fit.get_forecast(steps=horizon)
    point_forecast = prediction.predicted_mean.values
    ci = prediction.conf_int(alpha=1 - confidence_level)
    lower, upper = ci.iloc[:, 0].values, ci.iloc[:, 1].values

    rows, truncated = _format_forecast(dates, point_forecast, lower, upper)
    return {
        "model": "SARIMA",
        "params": {"order": list(order), "seasonal_order": list(seasonal_order)},
        "aic": round(float(fit.aic), 2),
        "bic": round(float(fit.bic), 2),
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": f"{int(confidence_level * 100)}% analytic confidence interval from the state-space model.",
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


def forecast_gradient_boosted_trees(
    df: pd.DataFrame,
    horizon: int = 30,
    lags: list = None,
    n_estimators: int = 200,
    max_depth: int = 3,
    learning_rate: float = 0.05,
) -> dict:
    """Retrain gradient-boosted trees on lag + calendar features using the
    FULL series, then forecast `horizon` steps ahead RECURSIVELY: each
    predicted value is fed back in as a lag feature for subsequent steps.

    This is a materially different (and riskier) evaluation setting than
    Layer 2's one-step-ahead backtest, which used TRUE lagged values at
    every point. Here, errors can compound over the horizon since later
    predictions depend on earlier ones being roughly correct. No native
    prediction interval is available for this approach.
    """
    lags = lags or [1, 7, 14]
    feat = _build_lag_features(df, lags)
    feature_cols = [f"lag_{lag}" for lag in lags] + ["day_of_week", "month", "time_index"]

    model = GradientBoostingRegressor(
        n_estimators=n_estimators, max_depth=max_depth, learning_rate=learning_rate, random_state=42
    )
    model.fit(feat[feature_cols], feat["value"])

    history = df[["date", "value"]].copy().reset_index(drop=True)
    future_dates = _future_dates(df, horizon)
    predictions = []

    for current_date in future_dates:
        row = {f"lag_{lag}": history["value"].iloc[-lag] for lag in lags}
        row["day_of_week"] = pd.Timestamp(current_date).dayofweek
        row["month"] = pd.Timestamp(current_date).month
        row["time_index"] = len(history)

        x_next = pd.DataFrame([row])[feature_cols]
        next_pred = float(model.predict(x_next)[0])
        predictions.append(next_pred)

        history = pd.concat(
            [history, pd.DataFrame({"date": [current_date], "value": [next_pred]})], ignore_index=True
        )

    importances = {col: round(float(imp), 4) for col, imp in zip(feature_cols, model.feature_importances_)}
    rows, truncated = _format_forecast(future_dates, predictions)

    return {
        "model": "Gradient Boosted Trees (recursive multi-step forecast)",
        "params": {"lags": lags, "n_estimators": n_estimators, "max_depth": max_depth, "learning_rate": learning_rate},
        "feature_importances": importances,
        "horizon": horizon,
        "forecast": rows,
        "truncated": truncated,
        "interval_note": "No native prediction interval for this model -- point forecast only.",
        "caveat": (
            "This is a RECURSIVE multi-step forecast: each prediction feeds back in as a lag "
            "feature for later steps, so errors can compound as the horizon grows. This "
            "compounding risk did not apply to Layer 2's evaluation of this same model type, "
            "which used true lagged values throughout -- treat longer horizons here with more "
            "skepticism than the equivalent SARIMA/ETS forecast."
        ),
    }
