"""
server.py — FastMCP server for the Layer 2 forecaster tools.

Wraps model_tools.py as typed MCP tools: fit a candidate model, backtest it
on a held-out window, and return error metrics plus diagnostics (AIC,
residual autocorrelation, feature importances) so the agent can reason
about model quality, not just chase the lowest error number.

Run over stdio (how OpenClaw will launch it), after `pip install -e .`:
    ts-forecaster-server
    # or: python -m omen.forecaster.server
"""

from typing import Optional

from fastmcp import FastMCP

from omen.data_prep import load_series
from .model_tools import (
    fit_naive_baselines as _fit_naive_baselines,
    fit_ets as _fit_ets,
    fit_sarima as _fit_sarima,
    fit_gradient_boosted_trees as _fit_gradient_boosted_trees,
    train_test_split as _train_test_split,
    diebold_mariano_test as _diebold_mariano_test,
    rolling_origin_backtest as _rolling_origin_backtest,
    search_sarima_orders as _search_sarima_orders,
)
from .plot_tools import (
    plot_backtest as _plot_backtest,
    plot_rolling_origin as _plot_rolling_origin,
    plot_search_sarima_orders as _plot_search_sarima_orders,
)

mcp = FastMCP("ts-forecaster")


@mcp.tool()
def holdout_split_summary(
    csv_path: str,
    holdout_size: int = 30,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Report the train/test date ranges for a given holdout size, without
    fitting anything. Call this first to sanity-check the split before
    fitting candidate models against it.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        holdout_size: Number of most-recent observations to hold out as the
            backtest window.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    train, test = _train_test_split(df, holdout_size)
    return {
        "n_total": len(df),
        "n_train": len(train),
        "n_test": len(test),
        "train_range": [str(train["date"].min().date()), str(train["date"].max().date())],
        "test_range": [str(test["date"].min().date()), str(test["date"].max().date())],
    }


@mcp.tool()
def fit_naive_baselines(
    csv_path: str,
    holdout_size: int = 30,
    seasonal_period: int = 7,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Fit two trivial baselines every real candidate model should beat:
    a flat naive forecast (repeat the last training value) and a seasonal
    naive forecast (repeat the value from `seasonal_period` steps back).
    Always run this first -- it's the floor any fancier model must clear.
    Each baseline's backtest metrics include a bootstrap confidence
    interval, and both include holdout_actuals/holdout_predicted so a
    later candidate can be compared against either baseline with
    diebold_mariano_test.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        holdout_size: Number of most-recent observations to backtest against.
        seasonal_period: Assumed seasonal cycle length for seasonal_naive.
        n_bootstrap: Bootstrap resamples for the backtest metrics' CIs.
        confidence_level: Confidence level for those CIs, e.g. 0.95 for 95%.
        seed: Random seed for the bootstrap, for reproducibility.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _fit_naive_baselines(
        df,
        holdout_size=holdout_size,
        seasonal_period=seasonal_period,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )


@mcp.tool()
def fit_ets(
    csv_path: str,
    holdout_size: int = 30,
    seasonal_period: int = 7,
    trend: str = "add",
    seasonal: str = "add",
    damped_trend: bool = False,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    n_simulations: int = 500,
    seed: int = 42,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Fit Holt-Winters exponential smoothing (ETS) on the training split,
    forecast the holdout window, and return backtest error metrics
    (including a bootstrap confidence interval) plus AIC/AICc (small-
    sample-corrected AIC -- prefer it over AIC) and a residual
    autocorrelation diagnostic (Ljung-Box, with its own effect size).
    Also simulates a prediction interval for the holdout and reports its
    empirical coverage against the real values (backtest_interval_coverage
    -- the same check ts-monitor__compare_forecast_to_actuals runs
    post-deployment, just run here first). Also returns
    holdout_actuals/holdout_predicted so this result can be compared
    against another model with diebold_mariano_test.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        holdout_size: Number of most-recent observations to backtest against.
        seasonal_period: Seasonal cycle length (e.g. 7 for weekly in daily data).
        trend: "add", "mul", or None.
        seasonal: "add", "mul", or None.
        damped_trend: Whether to damp the trend component.
        n_bootstrap: Bootstrap resamples for the backtest metrics' CI.
        confidence_level: Confidence level for that CI and the prediction
            interval coverage check, e.g. 0.95 for 95%.
        n_simulations: Simulated future paths used to build the backtest
            prediction interval.
        seed: Random seed for the bootstrap, for reproducibility.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _fit_ets(
        df,
        holdout_size=holdout_size,
        seasonal_period=seasonal_period,
        trend=trend,
        seasonal=seasonal,
        damped_trend=damped_trend,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        n_simulations=n_simulations,
        seed=seed,
    )


@mcp.tool()
def fit_sarima(
    csv_path: str,
    holdout_size: int = 30,
    order: Optional[list] = None,
    seasonal_order: Optional[list] = None,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Fit a SARIMA model on the training split, forecast the holdout
    window, and return backtest error metrics (including a bootstrap
    confidence interval) plus AIC/AICc/BIC (AICc is the small-sample-
    corrected AIC -- prefer it over AIC) and a residual autocorrelation
    diagnostic (Ljung-Box, with its own effect size). Also computes the
    analytic prediction interval for the holdout and reports its
    empirical coverage against the real values (backtest_interval_coverage
    -- the same check ts-monitor__compare_forecast_to_actuals runs
    post-deployment, just run here first). Also returns
    holdout_actuals/holdout_predicted so this result can be compared
    against another model with diebold_mariano_test.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        holdout_size: Number of most-recent observations to backtest against.
        order: [p, d, q] non-seasonal ARIMA order. Defaults to [1, 1, 1].
        seasonal_order: [P, D, Q, s] seasonal order. Defaults to [1, 1, 1, 7].
        n_bootstrap: Bootstrap resamples for the backtest metrics' CI.
        confidence_level: Confidence level for that CI and the prediction
            interval coverage check, e.g. 0.95 for 95%.
        seed: Random seed for the bootstrap, for reproducibility.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _fit_sarima(
        df,
        holdout_size=holdout_size,
        order=order,
        seasonal_order=seasonal_order,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )


@mcp.tool()
def fit_gradient_boosted_trees(
    csv_path: str,
    holdout_size: int = 30,
    lags: Optional[list] = None,
    n_estimators: int = 200,
    max_depth: int = 3,
    learning_rate: float = 0.05,
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Fit gradient-boosted trees on lag + calendar features and backtest
    on the holdout window. NOTE: this is evaluated one-step-ahead using
    true lagged values, not a recursive multi-step forecast -- it is an
    easier evaluation setting than fit_ets/fit_sarima above, and the tool
    result flags this explicitly. Don't compare its error numbers directly
    against ETS/SARIMA without accounting for that. Backtest metrics
    include a bootstrap confidence interval; holdout_actuals/
    holdout_predicted let this result be compared against another model
    with diebold_mariano_test (pass n_lags=0 there, since this backtest's
    errors are one-step-ahead, not genuinely autocorrelated the way a
    multi-step forecast's are).

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        holdout_size: Number of most-recent observations to backtest against.
        lags: List of lag steps to use as features. Defaults to [1, 7, 14].
        n_estimators: Number of boosting stages.
        max_depth: Max depth per tree.
        learning_rate: Shrinkage rate applied to each tree's contribution.
        n_bootstrap: Bootstrap resamples for the backtest metrics' CI.
        confidence_level: Confidence level for that CI, e.g. 0.95 for 95%.
        seed: Random seed for the bootstrap, for reproducibility.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _fit_gradient_boosted_trees(
        df,
        holdout_size=holdout_size,
        lags=lags,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        n_bootstrap=n_bootstrap,
        confidence_level=confidence_level,
        seed=seed,
    )


@mcp.tool()
def diebold_mariano_test(
    actuals: list,
    predicted_a: list,
    predicted_b: list,
    model_a_name: str = "Model A",
    model_b_name: str = "Model B",
    loss: str = "squared",
    n_lags: Optional[int] = None,
) -> dict:
    """Diebold-Mariano-style test (Diebold & Mariano, 1995) for whether
    two models' forecasts on the SAME holdout have significantly
    different accuracy -- gives "compare candidates honestly" actual
    statistical backing instead of eyeballing two error numbers. Without
    this, "SARIMA's MAPE is 4.8% vs seasonal_naive's 5.0%" has no way to
    tell a real difference from noise in a holdout that's often only
    ~30 points.

    Pass `actuals` (the holdout_actuals from either fit_* result being
    compared -- both must have used the SAME csv_path/holdout_size) and
    each model's holdout_predicted. A negative mean_loss_differential
    favors model A; positive favors model B.

    Uses a Newey-West (Bartlett-kernel) HAC-robust variance estimate of
    the mean loss differential, with n_lags defaulting to the standard
    Newey & West (1994) automatic rule -- appropriate for a genuinely
    multi-step backtest (fit_ets/fit_sarima), where later-horizon errors
    are typically autocorrelated with earlier ones. Pass n_lags=0 when
    BOTH models being compared are one-step-ahead backtests (e.g. two
    fit_gradient_boosted_trees runs), where that autocorrelation isn't
    expected. Uses a Student's t reference distribution (df = n - 1),
    a standard conservative choice for small holdout sizes.

    IMPORTANT: comparing fit_ets/fit_sarima (genuinely multi-step)
    against fit_gradient_boosted_trees (one-step-ahead) with this test
    tells you whether the error numbers differ significantly -- it does
    NOT resolve the apples-to-oranges evaluation-setting mismatch
    documented on fit_gradient_boosted_trees itself. Carry that caveat
    forward regardless of what this test says.

    Args:
        actuals: The real holdout values (same for both models).
        predicted_a: Model A's predictions on the same holdout.
        predicted_b: Model B's predictions on the same holdout.
        model_a_name: Label for model A in the result, e.g. "SARIMA".
        model_b_name: Label for model B in the result, e.g. "seasonal_naive".
        loss: "squared" (default) or "absolute".
        n_lags: Newey-West truncation lag. Defaults to the automatic
            Newey & West (1994) rule; pass 0 to assume independent errors.
    """
    return _diebold_mariano_test(
        actuals,
        predicted_a,
        predicted_b,
        model_a_name=model_a_name,
        model_b_name=model_b_name,
        loss=loss,
        n_lags=n_lags,
    )


@mcp.tool()
def rolling_origin_backtest(
    csv_path: str,
    model_type: str,
    params: Optional[dict] = None,
    holdout_size: int = 30,
    n_origins: int = 5,
    n_bootstrap: int = 200,
    seed: int = 42,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Walk-forward (expanding-window) backtest: repeat fit_ets/fit_sarima/
    fit_gradient_boosted_trees at n_origins different points in the
    series instead of evaluating against a single fixed holdout window.
    A single fixed holdout is one arbitrarily-chosen slice -- if it
    happened to contain an anomaly, or the trend/seasonality lined up
    unusually well or badly for one model, every metric computed from it
    (including that call's own bootstrap CI, which only resamples points
    WITHIN that one window) inherits the bias. This reports the
    distribution of backtest performance (mean, std, per-origin detail)
    across multiple non-overlapping origins -- a genuine measure of how
    STABLE a model's performance is across different stretches of the
    series, not a single snapshot.

    model_type must be "ets", "sarima", or "gbt" (not "naive" -- the
    naive baselines don't need walk-forward validation). Each origin
    refits the model from scratch: this is n_origins times the compute
    of a single fit_* call, by design.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        model_type: "ets", "sarima", or "gbt".
        params: Keyword arguments for the matching fit_* function, e.g.
            for "sarima": {"order": [1,1,1], "seasonal_order": [1,1,1,7]}.
        holdout_size: Test window size at each origin.
        n_origins: How many non-overlapping origins to evaluate.
        n_bootstrap: Bootstrap resamples for each origin's OWN backtest
            metric CI (kept modest by default since this runs n_origins
            times; the cross-origin mean/std is the headline measure).
        seed: Random seed, for reproducibility.
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _rolling_origin_backtest(
        df,
        model_type=model_type,
        params=params,
        holdout_size=holdout_size,
        n_origins=n_origins,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )


@mcp.tool()
def search_sarima_orders(
    csv_path: str,
    holdout_size: int = 30,
    seasonal_period: int = 7,
    d: int = 1,
    seasonal_d: int = 1,
    max_p: int = 2,
    max_q: int = 2,
    max_seasonal_p: int = 1,
    max_seasonal_q: int = 1,
    top_n: int = 5,
    max_combinations: int = 60,
    n_bootstrap_per_candidate: int = 200,
    date_col: str = "date",
    value_col: str = "value",
) -> dict:
    """Advisory grid search over SARIMA (p,q)(P,Q) combinations -- d and
    seasonal_d are held FIXED (pass them explicitly, informed by
    ts-analyst's stationarity findings; don't accept the defaults
    blindly), while p, q, P, Q are searched. Ranked by AICc where
    available (falling back to AIC), reusing fit_sarima for every
    candidate.

    THIS IS A SHORTLIST, NOT AN AUTHORITY. Reasoning about model settings
    from ts-analyst's findings is still your job (see this skill's Step
    3) -- this tool doesn't replace that. A numerically-best AICc
    candidate can still have structurally deficient residuals (check
    residual_diagnostics on whichever candidate you pick, via a direct
    fit_sarima call), or be a razor-thin winner over the next candidate
    (consider diebold_mariano_test if the top two are close).

    Bounded by max_combinations (default 60) to avoid runaway compute --
    each candidate is a full SARIMA fit. Combinations that fail to
    converge are skipped and counted, not treated as an error.

    Args:
        csv_path: Path to a CSV with a date column and a value column.
        holdout_size: Backtest window size for every candidate.
        seasonal_period: Seasonal cycle length (the `s` in [P,D,Q,s]).
        d: Non-seasonal differencing order, held fixed across the search.
        seasonal_d: Seasonal differencing order, held fixed.
        max_p: Search p in range(0, max_p + 1).
        max_q: Search q in range(0, max_q + 1).
        max_seasonal_p: Search P in range(0, max_seasonal_p + 1).
        max_seasonal_q: Search Q in range(0, max_seasonal_q + 1).
        top_n: How many top candidates to return in full.
        max_combinations: Safety cap on grid size; errors instead of
            running if the requested ranges would exceed it.
        n_bootstrap_per_candidate: Bootstrap resamples for each
            candidate's own metric CI (kept modest since this runs many
            fits).
        date_col: Name of the date column in the CSV.
        value_col: Name of the value column in the CSV.
    """
    df = load_series(csv_path, date_col, value_col)
    return _search_sarima_orders(
        df,
        holdout_size=holdout_size,
        seasonal_period=seasonal_period,
        d=d,
        seasonal_d=seasonal_d,
        max_p=max_p,
        max_q=max_q,
        max_seasonal_p=max_seasonal_p,
        max_seasonal_q=max_seasonal_q,
        top_n=top_n,
        max_combinations=max_combinations,
        n_bootstrap_per_candidate=n_bootstrap_per_candidate,
    )


@mcp.tool()
def plot_backtest(
    actuals: list,
    predicted: list,
    model_name: str = "Model",
    lower: Optional[list] = None,
    upper: Optional[list] = None,
    out_path: Optional[str] = None,
):
    """Plot actual vs. predicted values over a backtest holdout, with a
    shaded prediction-interval band if lower/upper bounds are supplied
    -- a visual complement to diebold_mariano_test's exact numbers, not
    a replacement for them. Returns the plot as an inline image plus a
    small status dict; also writes a PNG to out_path if given.

    Pass the SAME holdout_actuals/holdout_predicted a fit_* result
    already returned (the same arrays diebold_mariano_test itself
    takes) -- this does not refit anything. lower/upper are optional
    since not every model has an interval (e.g.
    fit_gradient_boosted_trees's backtest has none).

    Args:
        actuals: The real holdout values.
        predicted: The model's predictions on the same holdout.
        model_name: Label for the predicted line, e.g. "SARIMA".
        lower: Optional prediction-interval lower bound per point.
        upper: Optional prediction-interval upper bound per point.
        out_path: If given, also writes the PNG to this path on disk.
    """
    return _plot_backtest(actuals, predicted, model_name=model_name, lower=lower, upper=upper, out_path=out_path)


@mcp.tool()
def plot_rolling_origin(origins: list, out_path: Optional[str] = None):
    """Plot per-origin MAPE across a rolling_origin_backtest's walk-forward
    origins, with a shaded band showing the mean +/- one std -- makes
    cross-origin instability visually obvious rather than requiring a
    reader to compare a table of numbers. Returns the plot as an inline
    image plus a small status dict; also writes a PNG to out_path if given.

    Pass rolling_origin_backtest's own `origins` field directly.

    Args:
        origins: The `origins` list from a rolling_origin_backtest result.
        out_path: If given, also writes the PNG to this path on disk.
    """
    return _plot_rolling_origin(origins, out_path=out_path)


@mcp.tool()
def plot_search_sarima_orders(top_candidates: list, out_path: Optional[str] = None):
    """Plot AICc by candidate SARIMA order as a bar chart, so a razor-thin
    margin between top candidates (easy to miss in a table of decimals)
    is visually obvious. Returns the plot as an inline image plus a
    small status dict; also writes a PNG to out_path if given.

    Pass search_sarima_orders' own `top_candidates` field directly.

    Args:
        top_candidates: The `top_candidates` list from a
            search_sarima_orders result.
        out_path: If given, also writes the PNG to this path on disk.
    """
    return _plot_search_sarima_orders(top_candidates, out_path=out_path)


def main():
    """Entry point for the `ts-forecaster-server` console script."""
    mcp.run()  # defaults to stdio transport, which is what OpenClaw expects


if __name__ == "__main__":
    main()
